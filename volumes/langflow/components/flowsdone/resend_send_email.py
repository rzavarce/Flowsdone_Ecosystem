"""Resend Enviar Email (Flowsdone): lets an Agent email a customer from Flowsdone's own domain.

Sending goes through Resend (https://resend.com) with a domain Flowsdone
verified once via DNS (SPF/DKIM), ideally a subdomain such as
mail.flowsdone.com so a noisy tenant can't hurt the main domain's
reputation. Customers of the platform don't connect or share anything.

Built for tool mode with the risky parts fixed on the canvas, not chosen
by the model: sender address and name, Reply-To (the business, so the
customer's answers reach it), optional BCC and footer. The Agent only picks
one recipient, the subject and the text; the text is sent as plain text and
as escaped HTML, so it can't inject markup. A per-run cap stops a looping
Agent from sending a burst of emails.

Appointment confirmations can carry an .ics attachment: the Google Calendar
components authenticate with a service account, which can't invite
attendees, so this is how the customer gets an "add to calendar" entry.
Times are written in UTC in the .ics, which every calendar client accepts
without a VTIMEZONE block.

Every send has an Idempotency-Key derived from its content: Agents retry
tool calls, and Resend returns the original email for a repeated key
(within 24h) instead of sending it twice. That also makes retrying on
429/5xx safe.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from langflow.custom import Component
from langflow.io import IntInput, MultilineInput, Output, SecretStrInput, StrInput
from langflow.schema import Data

_EMAIL = re.compile(r"^[^@\s<>,;\"]+@[^@\s<>,;\"]+\.[^@\s<>,;\"]+$")
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_ICS_LINE_OCTETS = 75
# Tool-mode inputs and their defaults; see `_reset_tool_arguments`.
_TOOL_ARGUMENT_DEFAULTS = {
    "to_email": "",
    "subject": "",
    "body": "",
    "appointment_start": "",
    "appointment_duration_minutes": 0,
    "appointment_title": "",
}


class EmailError(ValueError):
    """A send request that can't be fulfilled; its message is meant for the Agent."""


class ResendSendEmailComponent(Component):
    display_name = "Resend Enviar Email (Flowsdone)"
    description = (
        "Envía un email a un cliente (un solo destinatario) desde el dominio de Flowsdone. Úsalo "
        "para confirmaciones o información que el cliente ha pedido recibir por correo. Si es la "
        "confirmación de una cita, indica su inicio para adjuntar el evento de calendario (.ics)."
    )
    name = "ResendSendEmail"
    icon = "Mail"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Resend API Key",
            required=True,
            info="API key de Resend, guardada como variable global (ej. FLOWSDONE_RESEND_KEY).",
        ),
        StrInput(
            name="from_email",
            display_name="Email remitente",
            required=True,
            info="Dirección de un dominio verificado en Resend (ej. 'citas@mail.flowsdone.com').",
        ),
        StrInput(
            name="from_name",
            display_name="Nombre remitente",
            info="Nombre que ve el cliente (ej. 'Clínica Sonrisa vía Flowsdone'). Vacío = solo la dirección.",
        ),
        StrInput(
            name="reply_to",
            display_name="Responder a",
            info="Email del negocio al que llegan las respuestas del cliente. Vacío = al remitente.",
        ),
        StrInput(
            name="bcc",
            display_name="Copia oculta (BCC)",
            advanced=True,
            info="Email que recibe copia de cada envío (ej. el del negocio). Vacío = sin copia.",
        ),
        MultilineInput(
            name="footer",
            display_name="Pie del email",
            advanced=True,
            info="Texto que se añade al final de cada email (firma, datos de contacto).",
        ),
        StrInput(
            name="timezone",
            display_name="Zona horaria",
            value="Europe/Madrid",
            info="Zona IANA en la que se interpreta el inicio de la cita (ej. 'Europe/Madrid').",
        ),
        IntInput(
            name="default_duration_minutes",
            display_name="Duración de cita por defecto (min)",
            value=30,
            advanced=True,
            info="Duración del evento .ics cuando el Agent no la indica.",
        ),
        IntInput(
            name="max_emails_per_run",
            display_name="Máximo de emails por ejecución",
            value=2,
            advanced=True,
            info="Tope de envíos en una misma ejecución del flujo, para que un Agent en bucle no haga spam.",
        ),
        StrInput(
            name="api_base_url",
            display_name="API base URL",
            value="https://api.resend.com",
            advanced=True,
        ),
        IntInput(name="timeout", display_name="Timeout (s)", value=15, advanced=True),
        StrInput(
            name="to_email",
            display_name="Para",
            tool_mode=True,
            info="Email del cliente destinatario (uno solo).",
        ),
        StrInput(
            name="subject",
            display_name="Asunto",
            tool_mode=True,
            info="Asunto del email, breve y claro.",
        ),
        MultilineInput(
            name="body",
            display_name="Cuerpo",
            tool_mode=True,
            info="Texto del email, sin HTML. Los saltos de línea se respetan.",
        ),
        StrInput(
            name="appointment_start",
            display_name="Inicio de la cita",
            tool_mode=True,
            info=(
                "Solo si el email confirma una cita: fecha y hora de inicio en hora local, formato "
                "'YYYY-MM-DDTHH:MM'. Se adjunta el evento para añadirlo al calendario. Vacío = sin adjunto."
            ),
        ),
        IntInput(
            name="appointment_duration_minutes",
            display_name="Duración de la cita (min)",
            value=0,
            tool_mode=True,
            info="Duración de la cita en minutos. 0 = duración por defecto.",
        ),
        StrInput(
            name="appointment_title",
            display_name="Título de la cita",
            tool_mode=True,
            info="Título del evento en el calendario del cliente (ej. 'Cita en Clínica Sonrisa'). Vacío = el asunto.",
        ),
    ]

    outputs = [
        Output(display_name="Resultado", name="result", method="send_email"),
    ]

    async def send_email(self) -> Data:
        """Sends the email, unless the request is invalid or the per-run cap was reached.

        Returns:
            Data: `success` plus, on success, `id` (Resend's email id), `to`
            and `calendar_attached`; on failure, `error`.
        """
        try:
            result = await self._send()
        except EmailError as exc:
            result = {"success": False, "error": str(exc)}
        finally:
            self._reset_tool_arguments()
        self.status = result
        return Data(data=result)

    def _reset_tool_arguments(self) -> None:
        """Puts the tool-mode inputs back to their defaults after a call.

        Langflow reuses this component instance for every call of the tool and
        only sets the arguments the Agent sent (LangChain drops the omitted
        ones), so an optional argument from a previous call would otherwise
        leak into the next one.
        """
        self.set(**_TOOL_ARGUMENT_DEFAULTS)

    async def _send(self) -> dict[str, Any]:
        """Validates, builds and posts the email to Resend.

        Returns:
            dict[str, Any]: The result payload returned by `send_email`.

        Raises:
            EmailError: If the request is invalid, over the cap, or Resend rejects it.
        """
        sent = getattr(self, "_emails_sent", 0)
        limit = int(self.max_emails_per_run or 0)
        if limit > 0 and sent >= limit:
            msg = f"Ya se enviaron {sent} emails en esta ejecución; no se envían más."
            raise EmailError(msg)

        payload = self._payload()
        key = self._idempotency_key(payload)
        response_data = await self._post(payload, key)
        self._emails_sent = sent + 1
        return {
            "success": True,
            "id": response_data.get("id"),
            "to": payload["to"][0],
            "calendar_attached": "attachments" in payload,
        }

    def _payload(self) -> dict[str, Any]:
        """Builds the Resend `POST /emails` body from the canvas config and the Agent's input.

        Returns:
            dict[str, Any]: The request body.

        Raises:
            EmailError: If a required field is missing or an address is invalid.
        """
        to_email = self._address(self.to_email, "Para", required=True)
        from_email = self._address(self.from_email, "Email remitente", required=True)
        reply_to = self._address(self.reply_to, "Responder a")
        bcc = self._address(self.bcc, "Copia oculta (BCC)")
        subject = " ".join((self.subject or "").split())
        body = (self.body or "").strip()
        if not subject:
            msg = "Falta el asunto del email."
            raise EmailError(msg)
        if not body:
            msg = "Falta el cuerpo del email."
            raise EmailError(msg)

        footer = (self.footer or "").strip()
        text = f"{body}\n\n--\n{footer}" if footer else body
        from_name = " ".join((self.from_name or "").replace('"', "").split())
        payload: dict[str, Any] = {
            "from": f'"{from_name}" <{from_email}>' if from_name else from_email,
            "to": [to_email],
            "subject": subject,
            "text": text,
            "html": self._html(body, footer),
        }
        if reply_to:
            payload["reply_to"] = reply_to
        if bcc:
            payload["bcc"] = [bcc]

        if (self.appointment_start or "").strip():
            ics = self._ics(to_email, from_email, from_name, subject, body)
            payload["attachments"] = [
                {
                    "filename": "cita.ics",
                    "content": base64.b64encode(ics.encode("utf-8")).decode("ascii"),
                    "content_type": "text/calendar; charset=utf-8; method=PUBLISH",
                }
            ]
        return payload

    @staticmethod
    def _address(value: str | None, field: str, *, required: bool = False) -> str | None:
        """Validates a single email address.

        Args:
            value (str | None): The raw value.
            field (str): Field name, for the error message.
            required (bool): Whether an empty value is an error.

        Returns:
            str | None: The trimmed address, or None if empty and not required.

        Raises:
            EmailError: If it's missing (when required), holds several addresses or isn't an email.
        """
        address = (value or "").strip()
        if not address:
            if required:
                msg = f"Falta '{field}'."
                raise EmailError(msg)
            return None
        if not _EMAIL.match(address):
            msg = f"'{field}' no es un email válido (uno solo): '{address}'."
            raise EmailError(msg)
        return address

    @staticmethod
    def _html(body: str, footer: str) -> str:
        """Renders the plain text as minimal, escaped HTML.

        Args:
            body (str): Email text.
            footer (str): Footer text (may be empty).

        Returns:
            str: HTML where every line break is kept and no markup from the input survives.
        """

        def paragraphs(text: str) -> str:
            return "".join(
                f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>" for block in re.split(r"\n\s*\n", text) if block
            )

        footer_html = (
            f'<hr style="border:none;border-top:1px solid #ddd"><div style="color:#666;font-size:13px">'
            f"{paragraphs(footer)}</div>"
            if footer
            else ""
        )
        return (
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#222">'
            f"{paragraphs(body)}{footer_html}</div>"
        )

    def _ics(self, to_email: str, from_email: str, from_name: str, subject: str, body: str) -> str:
        """Builds an iCalendar (RFC 5545) event for the appointment.

        The UID depends on the recipient and start, so resending a confirmation
        for the same appointment updates the entry in the customer's calendar
        instead of adding a second one.

        Args:
            to_email (str): Customer's email.
            from_email (str): Sender address (the organizer).
            from_name (str): Sender display name (may be empty).
            subject (str): Email subject, the fallback event title.
            body (str): Email text, used as the event description.

        Returns:
            str: The .ics content, CRLF line endings.

        Raises:
            EmailError: If the start, duration or time zone are invalid.
        """
        tz_name = (self.timezone or "").strip()
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            msg = f"Zona horaria no válida: '{self.timezone}'."
            raise EmailError(msg) from exc
        raw = (self.appointment_start or "").strip()
        try:
            start = datetime.fromisoformat(raw)
        except ValueError as exc:
            msg = f"Inicio de la cita no válido: '{raw}'. Usa el formato 'YYYY-MM-DDTHH:MM'."
            raise EmailError(msg) from exc
        start = start.replace(tzinfo=tz) if start.tzinfo is None else start.astimezone(tz)
        minutes = int(self.appointment_duration_minutes or 0) or int(self.default_duration_minutes or 0)
        if minutes <= 0:
            msg = "La duración de la cita debe ser mayor que 0 minutos."
            raise EmailError(msg)
        end = start + timedelta(minutes=minutes)

        def utc(moment: datetime) -> str:
            return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{to_email.lower()}|{start.isoformat()}")
        title = (self.appointment_title or "").strip() or subject
        organizer_cn = f";CN={self._ics_param(from_name)}" if from_name else ""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Flowsdone//Citas//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{uid}@flowsdone.com",
            f"DTSTAMP:{utc(datetime.now(timezone.utc))}",
            f"DTSTART:{utc(start)}",
            f"DTEND:{utc(end)}",
            f"SUMMARY:{self._ics_text(title)}",
            f"DESCRIPTION:{self._ics_text(body)}",
            f"ORGANIZER{organizer_cn}:mailto:{from_email}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "".join(f"{self._fold(line)}\r\n" for line in lines)

    @staticmethod
    def _ics_text(value: str) -> str:
        """Escapes a TEXT value for iCalendar.

        Args:
            value (str): Raw text.

        Returns:
            str: Text with backslash, ';', ',' and newlines escaped.
        """
        return (
            value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")
        )

    @staticmethod
    def _ics_param(value: str) -> str:
        """Quotes a parameter value (e.g. CN) for iCalendar.

        Args:
            value (str): Raw value.

        Returns:
            str: The value in double quotes, without characters a quoted parameter can't hold.
        """
        return '"' + re.sub(r'["\r\n]', "", value) + '"'

    @staticmethod
    def _fold(line: str) -> str:
        """Folds a content line at 75 octets, as RFC 5545 requires.

        Args:
            line (str): One unfolded content line.

        Returns:
            str: The line, split with CRLF + space without breaking UTF-8 characters.
        """
        parts, current, size = [], "", 0
        for char in line:
            octets = len(char.encode("utf-8"))
            limit = _ICS_LINE_OCTETS if not parts else _ICS_LINE_OCTETS - 1
            if size + octets > limit:
                parts.append(current)
                current, size = "", 0
            current += char
            size += octets
        parts.append(current)
        return "\r\n ".join(parts)

    @staticmethod
    def _idempotency_key(payload: dict[str, Any]) -> str:
        """Key that identifies this exact email for Resend's 24h deduplication.

        Args:
            payload (dict[str, Any]): The request body.

        Returns:
            str: 'flowsdone-' plus a SHA-256 of the recipient, sender, subject, text and attachment.
        """
        attachment = payload.get("attachments", [{}])[0].get("content", "")
        material = "\n".join([payload["from"], payload["to"][0], payload["subject"], payload["text"], attachment])
        return "flowsdone-" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    async def _post(self, payload: dict[str, Any], key: str) -> dict[str, Any]:
        """Posts the email to Resend, retrying 429/5xx and network errors.

        Args:
            payload (dict[str, Any]): The request body.
            key (str): Idempotency key, which makes the retries safe.

        Returns:
            dict[str, Any]: Resend's JSON response (holds the email `id`).

        Raises:
            EmailError: If Resend rejects the email or can't be reached.
        """
        url = f"{(self.api_base_url or 'https://api.resend.com').rstrip('/')}/emails"
        headers = {"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": key}
        last_error = ""
        async with httpx.AsyncClient(timeout=self.timeout or 15) as client:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.RequestError as exc:
                    last_error = f"No se pudo conectar con Resend: {exc}"
                else:
                    if response.status_code < 300:
                        return response.json()
                    last_error = self._describe_error(response)
                    if response.status_code not in _RETRYABLE:
                        raise EmailError(last_error)
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(0.5 * 2 ** (attempt - 1))
        raise EmailError(last_error)

    @staticmethod
    def _describe_error(response: Any) -> str:
        """Turns a Resend error response into a short message.

        Args:
            response (Any): The httpx response.

        Returns:
            str: HTTP status plus Resend's own message when there is one.
        """
        try:
            detail = response.json().get("message", "")
        except ValueError:
            detail = response.text[:200]
        if response.status_code in (401, 403):
            return f"Resend rechazó la API key o el remitente (HTTP {response.status_code}): {detail}"
        return f"Resend respondió con error HTTP {response.status_code}: {detail}"
