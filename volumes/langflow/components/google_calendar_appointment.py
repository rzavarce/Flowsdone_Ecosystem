"""Google Calendar Crear Cita (Flowsdone): lets an Agent book an appointment in a Google Calendar.

Authentication is a Google Cloud service account whose JSON key is kept in a
Langflow global variable (never in the flow): the calendar owner shares
their calendar with the service account's email ("Make changes to events"),
so no OAuth consent or token refresh is involved. The trade-off: without
Google Workspace domain-wide delegation, a service account can't invite
attendees, so the customer's details go in the event description and the
Agent confirms the appointment through the chat instead.

Built for tool mode: the Agent only fills the appointment itself (start,
duration, customer, reason); the calendar, time zone, business hours and
credentials are fixed on the canvas, so the model can't book into another
calendar or outside opening hours.

Before creating anything it checks the calendar's free/busy for that day:
if the slot overlaps an existing event, nothing is created and the Agent
gets the day's busy slots back to offer another time. Agents also retry
tool calls, so the event id is derived from calendar + start + customer:
asking twice for the same appointment returns the existing event instead
of booking it twice.

Like HTTP Request (Flowsdone), it never breaks the flow on a booking
problem: success and failure come back in the same shape, with a message
the Agent can relay.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langflow.custom import Component
from langflow.io import IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data

_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_ID_NAMESPACE = uuid.NAMESPACE_URL
_HOURS = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")
_HTTP_CONFLICT = 409
_HTTP_NOT_FOUND = 404
_HTTP_FORBIDDEN = 403


class BookingError(ValueError):
    """A booking request that can't be fulfilled; its message is meant for the Agent."""


class GoogleCalendarAppointmentComponent(Component):
    display_name = "Google Calendar Crear Cita (Flowsdone)"
    description = (
        "Crea una cita en la agenda de Google Calendar. Antes de crearla comprueba que el hueco "
        "esté libre: si está ocupado no crea nada y devuelve los tramos ocupados de ese día para "
        "proponer otra hora. Las horas se interpretan en la zona horaria de la agenda."
    )
    name = "GoogleCalendarAppointment"
    icon = "Google"

    inputs = [
        SecretStrInput(
            name="service_account_json",
            display_name="Service account (JSON)",
            required=True,
            info=(
                "Contenido del JSON de la cuenta de servicio de Google Cloud, guardado como variable "
                "global. El calendario debe estar compartido con el client_email de esa cuenta, con "
                "permiso 'Hacer cambios en eventos'."
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
            info="Zona IANA en la que se interpretan las horas que pide el cliente (ej. 'Europe/Madrid').",
        ),
        IntInput(
            name="default_duration_minutes",
            display_name="Duración por defecto (min)",
            value=30,
            info="Se usa cuando el Agent no indica duración.",
        ),
        StrInput(
            name="business_hours",
            display_name="Horario de citas",
            advanced=True,
            info="Tramo en el que se aceptan citas, ej. '09:00-18:00'. Vacío = cualquier hora.",
        ),
        StrInput(
            name="business_days",
            display_name="Días de citas",
            advanced=True,
            info="Días de la semana en que se aceptan citas, 1=lunes … 7=domingo, ej. '1,2,3,4,5'. Vacío = todos.",
        ),
        StrInput(
            name="title_template",
            display_name="Título del evento",
            value="Cita: {customer_name}",
            advanced=True,
            info="Plantilla del título. Admite {customer_name} y {reason}.",
        ),
        StrInput(
            name="start_datetime",
            display_name="Inicio",
            tool_mode=True,
            info=(
                "Fecha y hora de inicio de la cita en hora local de la agenda, formato "
                "'YYYY-MM-DDTHH:MM' (ej. '2026-10-02T10:30')."
            ),
        ),
        IntInput(
            name="duration_minutes",
            display_name="Duración (min)",
            value=0,
            tool_mode=True,
            info="Duración de la cita en minutos. 0 = duración por defecto de la agenda.",
        ),
        StrInput(
            name="customer_name",
            display_name="Nombre del cliente",
            tool_mode=True,
            info="Nombre y apellido de la persona que pide la cita.",
        ),
        StrInput(
            name="customer_contact",
            display_name="Contacto del cliente",
            tool_mode=True,
            info="Teléfono o email del cliente, para poder contactarle.",
        ),
        StrInput(
            name="reason",
            display_name="Motivo",
            tool_mode=True,
            info="Motivo o tema de la cita, en una frase.",
        ),
    ]

    outputs = [
        Output(display_name="Cita", name="appointment", method="create_appointment"),
    ]

    async def create_appointment(self) -> Data:
        """Books the requested appointment, unless the slot is taken or out of hours.

        Returns:
            Data: `success` plus, on success, `event_id`, `start`, `end`,
            `html_link` and `already_existed`; on failure, `error` and, if the
            slot was taken, `busy` (the day's busy slots as 'HH:MM-HH:MM').
        """
        try:
            result = await asyncio.to_thread(self._book)
        except BookingError as exc:
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

    def _book(self) -> dict[str, Any]:
        """Runs the booking synchronously (the Google client is blocking).

        Returns:
            dict[str, Any]: The result payload returned by `create_appointment`.

        Raises:
            BookingError: If the request is invalid, out of hours or the slot is busy.
            HttpError: If Google Calendar rejects a call.
        """
        tz = self._zone()
        start = self._parse_start(tz)
        end = start + timedelta(minutes=self._duration())
        customer_name = (self.customer_name or "").strip()
        if not customer_name:
            msg = "Falta el nombre del cliente."
            raise BookingError(msg)
        if start <= datetime.now(tz):
            msg = f"La hora pedida ({start:%Y-%m-%d %H:%M}) ya pasó."
            raise BookingError(msg)
        self._check_business_rules(start, end)

        service = self._build_service()
        event_id = self._event_id(start, customer_name)
        existing = self._get_event(service, event_id)
        if existing is not None and existing.get("status") != "cancelled":
            return self._success(existing, already_existed=True)

        busy = self._busy_slots(service, start, tz)
        if any(slot_start < end and start < slot_end for slot_start, slot_end in busy):
            return {
                "success": False,
                "error": f"El hueco {start:%Y-%m-%d %H:%M}-{end:%H:%M} está ocupado.",
                "busy": [f"{s:%H:%M}-{e:%H:%M}" for s, e in busy],
            }

        body = self._event_body(event_id, start, end, customer_name)
        events = service.events()
        if existing is not None:
            # A cancelled event keeps its id reserved: revive it instead of inserting.
            created = events.update(calendarId=self.calendar_id, eventId=event_id, body=body).execute()
        else:
            created = events.insert(calendarId=self.calendar_id, body=body).execute()
        return self._success(created, already_existed=False)

    def _zone(self) -> ZoneInfo:
        """Resolves the configured time zone.

        Returns:
            ZoneInfo: The calendar's time zone.

        Raises:
            BookingError: If `timezone` isn't a valid IANA name.
        """
        try:
            return ZoneInfo((self.timezone or "").strip())
        except (ZoneInfoNotFoundError, ValueError) as exc:
            msg = f"Zona horaria no válida: '{self.timezone}'."
            raise BookingError(msg) from exc

    def _parse_start(self, tz: ZoneInfo) -> datetime:
        """Parses `start_datetime` as local time in `tz` (an explicit offset is converted).

        Args:
            tz (ZoneInfo): The calendar's time zone.

        Returns:
            datetime: The timezone-aware start.

        Raises:
            BookingError: If the value is missing or not an ISO date-time.
        """
        raw = (self.start_datetime or "").strip()
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            msg = f"Inicio no válido: '{raw}'. Usa el formato 'YYYY-MM-DDTHH:MM'."
            raise BookingError(msg) from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)

    def _duration(self) -> int:
        """Minutes the appointment lasts.

        Returns:
            int: `duration_minutes`, or `default_duration_minutes` if not set.

        Raises:
            BookingError: If the resulting duration isn't positive.
        """
        minutes = int(self.duration_minutes or 0) or int(self.default_duration_minutes or 0)
        if minutes <= 0:
            msg = "La duración de la cita debe ser mayor que 0 minutos."
            raise BookingError(msg)
        return minutes

    def _check_business_rules(self, start: datetime, end: datetime) -> None:
        """Rejects appointments outside the configured days and hours.

        Args:
            start (datetime): Appointment start, in the calendar's time zone.
            end (datetime): Appointment end, in the calendar's time zone.

        Raises:
            BookingError: If the appointment falls outside them, or they're misconfigured.
        """
        days_raw = (self.business_days or "").strip()
        if days_raw:
            try:
                days = {int(day) for day in days_raw.split(",") if day.strip()}
            except ValueError as exc:
                msg = f"'Días de citas' no válido: '{days_raw}'."
                raise BookingError(msg) from exc
            if start.isoweekday() not in days:
                msg = f"No se dan citas ese día ({start:%Y-%m-%d})."
                raise BookingError(msg)

        hours_raw = (self.business_hours or "").strip()
        if not hours_raw:
            return
        match = _HOURS.match(hours_raw)
        if not match:
            msg = f"'Horario de citas' no válido: '{hours_raw}'. Usa 'HH:MM-HH:MM'."
            raise BookingError(msg)
        opens = time(int(match[1]), int(match[2]))
        closes = time(int(match[3]), int(match[4]))
        if start.time() < opens or end.date() != start.date() or end.time() > closes:
            msg = f"La cita debe estar dentro del horario {opens:%H:%M}-{closes:%H:%M}."
            raise BookingError(msg)

    def _build_service(self) -> Any:
        """Builds the Calendar v3 client from the service account key.

        Returns:
            Any: A googleapiclient Resource for Calendar v3.

        Raises:
            BookingError: If the key isn't valid service account JSON.
        """
        try:
            info = json.loads(self.service_account_json or "")
            credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            msg = "La credencial de la cuenta de servicio no es un JSON válido de Google Cloud."
            raise BookingError(msg) from exc
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _event_id(self, start: datetime, customer_name: str) -> str:
        """Deterministic event id, so a retried tool call doesn't book twice.

        Google accepts ids made of base32hex characters (a-v, 0-9); a uuid5's
        hex digits are a subset of those.

        Args:
            start (datetime): Appointment start.
            customer_name (str): Customer's name.

        Returns:
            str: The event id.
        """
        contact = (self.customer_contact or "").strip().lower()
        key = f"{self.calendar_id}|{start.isoformat()}|{customer_name.lower()}|{contact}"
        return uuid.uuid5(_ID_NAMESPACE, key).hex

    def _get_event(self, service: Any, event_id: str) -> dict | None:
        """Fetches an event by id.

        Args:
            service (Any): Calendar v3 client.
            event_id (str): The event id.

        Returns:
            dict | None: The event, or None if it doesn't exist.
        """
        try:
            return service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()
        except HttpError as exc:
            if exc.resp.status == _HTTP_NOT_FOUND:
                return None
            raise

    def _busy_slots(self, service: Any, start: datetime, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
        """Busy slots of the calendar for the whole local day of `start`.

        Args:
            service (Any): Calendar v3 client.
            start (datetime): Appointment start; its local day is queried.
            tz (ZoneInfo): The calendar's time zone.

        Returns:
            list[tuple[datetime, datetime]]: Busy (start, end) pairs, in `tz`.
        """
        day_start = datetime.combine(start.date(), time.min, tzinfo=tz)
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
            raise BookingError(msg)
        return [
            (
                datetime.fromisoformat(slot["start"].replace("Z", "+00:00")).astimezone(tz),
                datetime.fromisoformat(slot["end"].replace("Z", "+00:00")).astimezone(tz),
            )
            for slot in calendar.get("busy", [])
        ]

    def _event_body(self, event_id: str, start: datetime, end: datetime, customer_name: str) -> dict[str, Any]:
        """Builds the Calendar event resource.

        Args:
            event_id (str): Deterministic event id.
            start (datetime): Appointment start.
            end (datetime): Appointment end.
            customer_name (str): Customer's name.

        Returns:
            dict[str, Any]: The event body for events.insert/update.
        """
        reason = (self.reason or "").strip()
        values = {"customer_name": customer_name, "reason": reason}
        try:
            summary = (self.title_template or "Cita: {customer_name}").format(**values)
        except (KeyError, IndexError, ValueError):
            summary = f"Cita: {customer_name}"
        lines = [
            f"Cliente: {customer_name}",
            f"Contacto: {(self.customer_contact or '').strip() or '-'}",
            f"Motivo: {reason or '-'}",
            "",
            "Creada por el asistente virtual de Flowsdone.",
        ]
        tz_name = str(start.tzinfo)
        return {
            "id": event_id,
            "status": "confirmed",
            "summary": summary,
            "description": "\n".join(lines),
            "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
        }

    def _success(self, event: dict, *, already_existed: bool) -> dict[str, Any]:
        """Shapes a successful booking for the Agent.

        Args:
            event (dict): The Calendar event resource.
            already_existed (bool): Whether the same appointment was already booked.

        Returns:
            dict[str, Any]: The success payload.
        """
        return {
            "success": True,
            "already_existed": already_existed,
            "event_id": event.get("id"),
            "start": event.get("start", {}).get("dateTime"),
            "end": event.get("end", {}).get("dateTime"),
            "html_link": event.get("htmlLink"),
        }

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
                "compartido con el email de la cuenta de servicio con permiso 'Hacer cambios en eventos'."
            )
        if status == _HTTP_CONFLICT:
            return "Google Calendar rechazó la cita por un conflicto de id; vuelve a intentarlo."
        return f"Google Calendar respondió con error HTTP {status}."
