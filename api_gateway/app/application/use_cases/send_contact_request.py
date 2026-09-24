"""Use case behind the landing page's contact form: email the request to
the Flowsdone team, with replies going straight to the person who wrote.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.domain.models.contact import ContactRequest
from app.domain.ports.outbound import EmailSenderPort, LoginThrottlePort

logger = logging.getLogger("usecase.send_contact_request")

INTEREST_LABELS = {
    "agents": "Agentes de IA para atención al cliente",
    "channels": "Atención multicanal (WhatsApp, Instagram, web…)",
    "voice": "Asistente telefónico de voz",
    "automation": "Automatización de procesos",
    "knowledge": "Asistente con la documentación de la empresa",
    "plans": "Planes y precios",
    "other": "Otro",
}


class ContactNotConfiguredError(Exception):
    """No recipient is configured for contact requests (maps to 503)."""


class TooManyContactRequestsError(Exception):
    """The sender's IP hit the limit of requests per window (maps to 429)."""


class SendContactRequestUseCase:
    """Emails a contact request to the team, limited per client IP."""

    def __init__(
        self,
        *,
        email_sender: EmailSenderPort,
        throttle: LoginThrottlePort,
        recipient: Optional[str],
        max_per_ip: int,
        window_seconds: int,
    ) -> None:
        """Build the use case.

        Args:
            email_sender (EmailSenderPort): Sends the email.
            throttle (LoginThrottlePort): Per-IP counters.
            recipient (Optional[str]): Who receives the requests; None
                disables the form.
            max_per_ip (int): Requests allowed per IP and window.
            window_seconds (int): Length of that window.
        """
        self._email = email_sender
        self._throttle = throttle
        self._recipient = recipient
        self._max_per_ip = max_per_ip
        self._window_seconds = window_seconds

    async def execute(self, request: ContactRequest, *, client_ip: Optional[str]) -> None:
        """Send the request to the team.

        Args:
            request (ContactRequest): What the prospect wrote.
            client_ip (Optional[str]): Their IP, for the rate limit.

        Raises:
            ContactNotConfiguredError: If there is no recipient.
            TooManyContactRequestsError: If the IP is over the limit.
            EmailSendError: If the email could not be sent.
        """
        if not self._recipient:
            raise ContactNotConfiguredError("CONTACT_EMAIL_TO is not configured")
        key = f"contact:ip:{client_ip or 'unknown'}"
        if await self._throttle.failures(key) >= self._max_per_ip:
            raise TooManyContactRequestsError()
        await self._throttle.record_failure(key, window_seconds=self._window_seconds)
        interest = INTEREST_LABELS[request.interest]
        who = f"{request.name} ({request.company})" if request.company else request.name
        who = " ".join(who.split())  # no line breaks in the subject header
        await self._email.send_template(
            to=self._recipient,
            template="contact_request",
            subject=f"Nuevo contacto desde la web: {who}",
            context={**request.model_dump(), "interest_label": interest},
            reply_to=request.email,
        )
        logger.info("contact.request_sent", extra={"interest": request.interest})
