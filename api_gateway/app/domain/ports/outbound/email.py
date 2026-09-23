"""Port for sending transactional emails (account activation, password reset).

The domain only knows it can send a named template with some data; which
provider (Resend), how the HTML is rendered (Jinja2) and where the templates
live are adapter concerns - see `adapters/outbound/email/`.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol


class EmailSendError(Exception):
    """Raised when the email could not be sent (provider error, network, ...).

    Use cases that provision a user let this propagate rather than undoing
    the user's creation - the account stays usable via a resend, instead of
    being silently lost because an email provider had a bad moment.
    """


class EmailSenderPort(Protocol):
    """Contract for sending a rendered email."""

    async def send_template(
        self,
        *,
        to: str,
        template: str,
        context: Dict[str, Any],
        subject: str,
    ) -> None:
        """Render a template and send it.

        Args:
            to (str): Recipient email address.
            template (str): Template name (without extension), resolved by
                the adapter inside its own templates directory.
            context (Dict[str, Any]): Data made available to the template.
            subject (str): Email subject line.

        Raises:
            EmailSendError: If the provider rejects the email or is
                unreachable.
        """
        ...
