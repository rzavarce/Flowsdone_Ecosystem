"""Google Calendar Disponibilidad (Flowsdone): lets an Agent see which times are free on a given day.

Companion of Google Calendar Crear Cita (Flowsdone): the Agent asks this one
for the free slots of a day, offers them to the customer, and books the
chosen one with the other. They're separate components on purpose: in
Langflow 1.4 every tool-mode input of a component becomes an argument of
every tool it exposes, so one component with both tools would ask the
Agent for customer details just to check availability.

Same authentication as the booking component (a service account JSON in a
Langflow global variable, with the calendar shared with its email; for
free/busy, "See only free/busy" is enough). Langflow loads each file in the
components folder on its own, so the small helpers both need (time zone,
credentials, free/busy query) are repeated here rather than imported.

The day is cut into candidate start times on a fixed grid (every
`slot_step_minutes` from the opening time), keeping those where an
appointment of the requested duration fits between busy slots, inside
business hours and not in the past.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langflow.custom import Component
from langflow.io import IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data

# Read-only is enough for free/busy; a key shared for booking works too.
_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_HOURS = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
_HTTP_NOT_FOUND = 404
_HTTP_FORBIDDEN = 403


class AvailabilityError(ValueError):
    """A request that can't be answered; its message is meant for the Agent."""


class GoogleCalendarAvailabilityComponent(Component):
    display_name = "Google Calendar Disponibilidad (Flowsdone)"
    description = (
        "Consulta los huecos libres de la agenda de Google Calendar en un día concreto, para "
        "ofrecer horas al cliente antes de crear la cita. Devuelve los tramos libres y las horas "
        "de inicio posibles para la duración pedida, en la zona horaria de la agenda."
    )
    name = "GoogleCalendarAvailability"
    icon = "Google"

    inputs = [
        SecretStrInput(
            name="service_account_json",
            display_name="Service account (JSON)",
            required=True,
            info=(
                "Contenido del JSON de la cuenta de servicio de Google Cloud, guardado como variable "
                "global. El calendario debe estar compartido con el client_email de esa cuenta."
            ),
        ),
        StrInput(
            name="calendar_id",
            display_name="ID del calendario",
            required=True,
            info="Normalmente el email de la cuenta de Google dueña de la agenda (ej. 'tu@gmail.com').",
        ),
        StrInput(
            name="timezone",
            display_name="Zona horaria",
            value="Europe/Madrid",
            required=True,
            info="Zona IANA de la agenda (ej. 'Europe/Madrid').",
        ),
        StrInput(
            name="business_hours",
            display_name="Horario de citas",
            value="09:00-18:00",
            info="Tramo del día en el que se ofrecen citas, ej. '09:00-18:00'. Vacío = el día entero.",
        ),
        StrInput(
            name="business_days",
            display_name="Días de citas",
            value="1,2,3,4,5",
            info="Días de la semana con citas, 1=lunes … 7=domingo. Vacío = todos.",
        ),
        IntInput(
            name="default_duration_minutes",
            display_name="Duración por defecto (min)",
            value=30,
            info="Se usa cuando el Agent no indica duración.",
        ),
        IntInput(
            name="slot_step_minutes",
            display_name="Intervalo entre horas (min)",
            value=30,
            advanced=True,
            info="Cada cuánto se ofrece una hora de inicio (30 = 09:00, 09:30, 10:00…).",
        ),
        StrInput(
            name="date",
            display_name="Fecha",
            tool_mode=True,
            info="Día a consultar, formato 'YYYY-MM-DD' (ej. '2026-10-02').",
        ),
        IntInput(
            name="duration_minutes",
            display_name="Duración (min)",
            value=0,
            tool_mode=True,
            info="Duración de la cita que se quiere encajar, en minutos. 0 = duración por defecto.",
        ),
    ]

    outputs = [
        Output(display_name="Disponibilidad", name="availability", method="check_availability"),
    ]

    async def check_availability(self) -> Data:
        """Finds the free slots of the requested day.

        Returns:
            Data: `success` plus, on success, `date`, `timezone`,
            `duration_minutes`, `free_ranges` ('HH:MM-HH:MM'),
            `available_starts` ('HH:MM') and, when there are none, a
            `message` saying why; on failure, `error`.
        """
        try:
            result = await asyncio.to_thread(self._check)
        except AvailabilityError as exc:
            result = {"success": False, "error": str(exc)}
        except HttpError as exc:
            result = {"success": False, "error": self._describe_http_error(exc)}
        except GoogleAuthError as exc:
            # Raised on the first API call: a revoked/deleted key, or a key from another project.
            result = {"success": False, "error": f"Google rechazó la credencial de la cuenta de servicio: {exc}"}
        except OSError as exc:
            result = {"success": False, "error": f"No se pudo conectar con Google Calendar: {exc}"}
        self.status = result
        return Data(data=result)

    def _check(self) -> dict[str, Any]:
        """Runs the lookup synchronously (the Google client is blocking).

        Returns:
            dict[str, Any]: The result payload returned by `check_availability`.

        Raises:
            AvailabilityError: If the request or the configuration is invalid.
            HttpError: If Google Calendar rejects a call.
        """
        tz = self._zone()
        day = self._parse_date()
        duration = timedelta(minutes=self._duration())
        step = timedelta(minutes=self._step())
        result: dict[str, Any] = {
            "success": True,
            "date": day.isoformat(),
            "timezone": str(tz),
            "duration_minutes": int(duration.total_seconds() // 60),
            "free_ranges": [],
            "available_starts": [],
        }

        now = datetime.now(tz)
        if day < now.date():
            msg = f"La fecha {day.isoformat()} ya pasó."
            raise AvailabilityError(msg)
        if not self._is_business_day(day):
            result["message"] = f"No se dan citas ese día ({day.isoformat()})."
            return result

        opens, closes = self._window(day, tz)
        # Today: only from the next grid slot after now.
        earliest = opens
        while earliest < now:
            earliest += step
        if earliest + duration > closes:
            result["message"] = "No quedan huecos libres ese día."
            return result

        busy = self._busy_slots(self._build_service(), day, tz)
        free_ranges = self._free_ranges(earliest, closes, busy, duration)
        starts = []
        for range_start, range_end in free_ranges:
            candidate = opens
            while candidate < range_start:
                candidate += step
            while candidate + duration <= range_end:
                starts.append(candidate)
                candidate += step

        result["free_ranges"] = [f"{s:%H:%M}-{self._hhmm(e, day)}" for s, e in free_ranges]
        result["available_starts"] = [f"{s:%H:%M}" for s in starts]
        if not starts:
            result["message"] = "No hay huecos libres ese día para esa duración."
        return result

    @staticmethod
    def _free_ranges(
        start: datetime, end: datetime, busy: list[tuple[datetime, datetime]], duration: timedelta
    ) -> list[tuple[datetime, datetime]]:
        """Subtracts busy slots from [start, end), keeping gaps long enough for `duration`.

        Args:
            start (datetime): Beginning of the searchable window.
            end (datetime): End of the searchable window.
            busy (list[tuple[datetime, datetime]]): Busy (start, end) pairs, any order, may overlap.
            duration (timedelta): Minimum length of a useful gap.

        Returns:
            list[tuple[datetime, datetime]]: Free (start, end) pairs, in order.
        """
        free = []
        cursor = start
        for busy_start, busy_end in sorted(busy):
            if busy_end <= cursor:
                continue
            if busy_start >= end:
                break
            if busy_start - cursor >= duration:
                free.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if end - cursor >= duration:
            free.append((cursor, end))
        return free

    @staticmethod
    def _hhmm(moment: datetime, day: date) -> str:
        """Formats a range end, showing midnight at the end of `day` as '24:00'.

        Args:
            moment (datetime): The time to format.
            day (date): The day being listed.

        Returns:
            str: 'HH:MM'.
        """
        return "24:00" if moment.date() > day and moment.time() == time.min else f"{moment:%H:%M}"

    def _zone(self) -> ZoneInfo:
        """Resolves the configured time zone.

        Returns:
            ZoneInfo: The calendar's time zone.

        Raises:
            AvailabilityError: If `timezone` isn't a valid IANA name.
        """
        try:
            return ZoneInfo((self.timezone or "").strip())
        except (ZoneInfoNotFoundError, ValueError) as exc:
            msg = f"Zona horaria no válida: '{self.timezone}'."
            raise AvailabilityError(msg) from exc

    def _parse_date(self) -> date:
        """Parses `date` ('YYYY-MM-DD'; a full date-time is accepted and its day used).

        Returns:
            date: The day to look up.

        Raises:
            AvailabilityError: If the value is missing or not an ISO date.
        """
        raw = (self.date or "").strip()
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError as exc:
            msg = f"Fecha no válida: '{raw}'. Usa el formato 'YYYY-MM-DD'."
            raise AvailabilityError(msg) from exc

    def _duration(self) -> int:
        """Minutes the appointment would last.

        Returns:
            int: `duration_minutes`, or `default_duration_minutes` if not set.

        Raises:
            AvailabilityError: If the resulting duration isn't positive.
        """
        minutes = int(self.duration_minutes or 0) or int(self.default_duration_minutes or 0)
        if minutes <= 0:
            msg = "La duración de la cita debe ser mayor que 0 minutos."
            raise AvailabilityError(msg)
        return minutes

    def _step(self) -> int:
        """Minutes between offered start times.

        Returns:
            int: `slot_step_minutes`.

        Raises:
            AvailabilityError: If it isn't positive.
        """
        minutes = int(self.slot_step_minutes or 0)
        if minutes <= 0:
            msg = "'Intervalo entre horas' debe ser mayor que 0 minutos."
            raise AvailabilityError(msg)
        return minutes

    def _is_business_day(self, day: date) -> bool:
        """Whether appointments are given on `day`.

        Args:
            day (date): The day to check.

        Returns:
            bool: True if `business_days` is empty or includes the day's ISO weekday.

        Raises:
            AvailabilityError: If `business_days` is misconfigured.
        """
        raw = (self.business_days or "").strip()
        if not raw:
            return True
        try:
            days = {int(value) for value in raw.split(",") if value.strip()}
        except ValueError as exc:
            msg = f"'Días de citas' no válido: '{raw}'."
            raise AvailabilityError(msg) from exc
        return day.isoweekday() in days

    def _window(self, day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
        """Opening and closing moments of `day`.

        Args:
            day (date): The day to look up.
            tz (ZoneInfo): The calendar's time zone.

        Returns:
            tuple[datetime, datetime]: (opens, closes); the whole day if `business_hours` is empty.

        Raises:
            AvailabilityError: If `business_hours` is misconfigured.
        """
        raw = (self.business_hours or "").strip()
        day_start = datetime.combine(day, time.min, tzinfo=tz)
        if not raw:
            return day_start, day_start + timedelta(days=1)
        match = _HOURS.match(raw)
        try:
            if not match:
                raise ValueError(raw)
            opens = datetime.combine(day, time(int(match[1]), int(match[2])), tzinfo=tz)
            closes = datetime.combine(day, time(int(match[3]), int(match[4])), tzinfo=tz)
        except ValueError as exc:
            msg = f"'Horario de citas' no válido: '{raw}'. Usa 'HH:MM-HH:MM'."
            raise AvailabilityError(msg) from exc
        if closes <= opens:
            msg = f"'Horario de citas' no válido: '{raw}'. El cierre debe ser posterior a la apertura."
            raise AvailabilityError(msg)
        return opens, closes

    def _build_service(self) -> Any:
        """Builds the Calendar v3 client from the service account key.

        Returns:
            Any: A googleapiclient Resource for Calendar v3.

        Raises:
            AvailabilityError: If the key isn't valid service account JSON.
        """
        try:
            info = json.loads(self.service_account_json or "")
            credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            msg = "La credencial de la cuenta de servicio no es un JSON válido de Google Cloud."
            raise AvailabilityError(msg) from exc
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _busy_slots(self, service: Any, day: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
        """Busy slots of the calendar for the whole local `day`.

        Args:
            service (Any): Calendar v3 client.
            day (date): The day to query.
            tz (ZoneInfo): The calendar's time zone.

        Returns:
            list[tuple[datetime, datetime]]: Busy (start, end) pairs, in `tz`.

        Raises:
            AvailabilityError: If Google reports an error for this calendar.
        """
        day_start = datetime.combine(day, time.min, tzinfo=tz)
        body = {
            "timeMin": day_start.isoformat(),
            "timeMax": (day_start + timedelta(days=1)).isoformat(),
            "timeZone": str(tz),
            "items": [{"id": self.calendar_id}],
        }
        response = service.freebusy().query(body=body).execute()
        calendar = response.get("calendars", {}).get(self.calendar_id, {})
        if calendar.get("errors"):
            reason = calendar["errors"][0].get("reason", "desconocido")
            msg = f"No se pudo consultar la disponibilidad del calendario ({reason})."
            raise AvailabilityError(msg)
        return [
            (
                datetime.fromisoformat(slot["start"].replace("Z", "+00:00")).astimezone(tz),
                datetime.fromisoformat(slot["end"].replace("Z", "+00:00")).astimezone(tz),
            )
            for slot in calendar.get("busy", [])
        ]

    def _describe_http_error(self, exc: HttpError) -> str:
        """Turns a Google API error into a message the Agent (and whoever reads the logs) can act on.

        Args:
            exc (HttpError): The error raised by the Google client.

        Returns:
            str: A short explanation.
        """
        status = exc.resp.status
        if status in (_HTTP_FORBIDDEN, _HTTP_NOT_FOUND):
            return (
                f"Sin acceso al calendario '{self.calendar_id}' (HTTP {status}). Comprueba que esté "
                "compartido con el email de la cuenta de servicio."
            )
        return f"Google Calendar respondió con error HTTP {status}."
