"""Port for registering a channel_connection's webhook with its
external platform.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class WebhookRegistrarPort(Protocol):
    """Registers the inbound webhook for a channel_connection with the
    external platform, so an admin never has to run the equivalent
    curl call by hand.

    Different platforms need different pieces of `credentials` to do
    this (Telegram needs a secret we generate ourselves; Meta needs
    the connection's own `page_access_token` and nothing we generate),
    so `register`/`deregister` receive the whole credentials dict
    rather than a single opaque value — each implementation reads
    whatever key its platform actually needs.

    Attributes:
        secret_field (Optional[str]): Key under which this channel's
            auto-generated webhook secret is stored in
            `channel_connections.credentials` (e.g.
            "telegram_webhook_secret"). None if this channel's
            registration does not need a secret we generate (e.g.
            Meta, which verifies webhooks with the shared
            `channel_apps.meta.app_secret` instead).
    """

    secret_field: Optional[str]

    async def register(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Register the webhook with the external platform.

        Args:
            external_id (str): Channel-specific identifier used to
                reach the platform's registration API (bot token, page
                id, etc., depending on the channel).
            credentials (Dict[str, Any]): The channel_connection's
                credentials; implementations read whatever key(s) they
                need from it (e.g. `secret_field` for Telegram,
                "page_access_token" for Meta).

        Raises:
            Exception: If the external platform rejects the
                registration (invalid external_id, unreachable API,
                etc.). Implementations should not swallow failures —
                the caller needs to know registration did not happen.
        """
        ...

    async def deregister(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Remove the webhook registration from the external platform.

        Called when the owning channel_connection is deleted, so the
        platform stops trying to call a URL we no longer resolve.
        Callers treat this as best-effort (log and proceed with the
        deletion either way), so implementations should raise on
        failure rather than swallow it — the caller decides how to
        react, not this port.

        Args:
            external_id (str): Channel-specific identifier used to
                reach the platform's registration API (bot token, page
                id, etc., depending on the channel).
            credentials (Dict[str, Any]): The channel_connection's
                credentials, in case deregistration needs them (e.g.
                Meta's `page_access_token`).

        Raises:
            Exception: If the external platform rejects the
                deregistration or is unreachable.
        """
        ...
