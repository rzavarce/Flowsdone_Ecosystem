"""Port for registering a channel_connection's webhook with its
external platform.
"""

from __future__ import annotations

from typing import Protocol


class WebhookRegistrarPort(Protocol):
    """Registers the inbound webhook for a channel_connection with the
    external platform, so an admin never has to run the equivalent
    curl call by hand.

    Attributes:
        secret_field (str): Key under which this channel's generated
            webhook secret is stored in `channel_connections.credentials`
            (e.g. "telegram_webhook_secret").
    """

    secret_field: str

    async def register(self, *, external_id: str, secret: str) -> None:
        """Register the webhook with the external platform.

        Args:
            external_id (str): Channel-specific identifier used to
                reach the platform's registration API (bot token, page
                id, etc., depending on the channel).
            secret (str): Shared secret the platform must echo back on
                every inbound webhook call, so it can be verified.

        Raises:
            Exception: If the external platform rejects the
                registration (invalid external_id, unreachable API,
                etc.). Implementations should not swallow failures —
                the caller needs to know registration did not happen.
        """
        ...

    async def deregister(self, *, external_id: str) -> None:
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

        Raises:
            Exception: If the external platform rejects the
                deregistration or is unreachable.
        """
        ...
