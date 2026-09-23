"""Resend implementation of EmailSenderPort.

Resend is a plain HTTPS REST API (https://resend.com/docs/api-reference/emails/send-email),
chosen specifically because the VPS has outbound SMTP blocked - this adapter
never opens an SMTP connection, only an HTTPS POST via httpx (already a
project dependency, same as the Langflow admin client).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import httpx
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.config import settings
from app.domain.ports.outbound.email import EmailSendError, EmailSenderPort

logger = logging.getLogger("email.resend_client")

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_API_URL = "https://api.resend.com/emails"


class ResendEmailAdapter(EmailSenderPort):
    """Renders a Jinja2 template and sends it through the Resend API."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Build the adapter.

        Args:
            client (httpx.AsyncClient | None): HTTP client to use; a fresh
                one pointing nowhere in particular is created when omitted
                (Resend's URL is absolute, so no `base_url` is needed).
        """
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "jinja"]),
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _render(self, template: str, context: Dict[str, Any]) -> str:
        """Render a template by name.

        Args:
            template (str): Name without extension (e.g. `account_activation`);
                resolved to `<name>.html.jinja` inside `templates/`.
            context (Dict[str, Any]): Data passed to the template.

        Returns:
            str: The rendered HTML.

        Raises:
            EmailSendError: If the template does not exist.
        """
        try:
            return self._env.get_template(f"{template}.html.jinja").render(**context)
        except TemplateNotFound as exc:
            raise EmailSendError(f"unknown email template: {template}") from exc

    async def send_template(
        self,
        *,
        to: str,
        template: str,
        context: Dict[str, Any],
        subject: str,
    ) -> None:
        """Render `template` and send it via the Resend API.

        Args:
            to (str): Recipient email address.
            template (str): Template name (see `_render`).
            context (Dict[str, Any]): Data made available to the template.
            subject (str): Email subject line.

        Raises:
            EmailSendError: If `RESEND_API_KEY` is not configured, the
                template is missing, or Resend rejects/cannot be reached.
        """
        if not settings.RESEND_API_KEY:
            raise EmailSendError("RESEND_API_KEY is not configured")
        html = self._render(template, context)
        body = {
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        try:
            response = await self._client.post(
                _API_URL,
                json=body,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
        except httpx.HTTPError as exc:
            raise EmailSendError(f"resend unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            logger.warning(
                "email.resend.rejected",
                extra={"status_code": response.status_code, "template": template},
            )
            raise EmailSendError(f"resend rejected the email (HTTP {response.status_code})")
