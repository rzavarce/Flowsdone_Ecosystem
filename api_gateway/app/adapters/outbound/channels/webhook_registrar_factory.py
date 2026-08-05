"""Factory that assembles all available webhook registrars."""

from __future__ import annotations

from typing import Dict

from ....domain.ports.outbound import WebhookRegistrarPort
from .telegram_webhook_registrar import TelegramWebhookRegistrar


class WebhookRegistrarFactory:
    """Builds the channel_type -> WebhookRegistrarPort map used by
    CreateChannelConnectionUseCase to auto-register a webhook right
    after creating a channel_connection, for channels that support it.

    Channels without an entry here simply keep the manual/curl flow —
    adding a new one is a one-line addition, no changes needed to the
    use case itself.
    """

    def build_all(self) -> Dict[str, WebhookRegistrarPort]:
        """Instantiate every supported webhook registrar.

        Returns:
            Dict[str, WebhookRegistrarPort]: A dict mapping each
            supported channel_type to its registrar.
        """
        return {
            "telegram": TelegramWebhookRegistrar(),
        }
