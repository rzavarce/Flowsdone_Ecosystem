"""Factory that assembles all available webhook registrars."""

from __future__ import annotations

from typing import Dict

from ....domain.ports.outbound import WebhookRegistrarPort
from .meta_webhook_registrar import MetaWebhookRegistrar
from .telegram_webhook_registrar import TelegramWebhookRegistrar

# Graph API fields to subscribe each Meta-backed channel to. Facebook
# Messenger also cares about postback/delivery/read events; Instagram
# DM (via the linked page) only needs "messages" today.
_FACEBOOK_SUBSCRIBED_FIELDS = "messages,messaging_postbacks,message_deliveries,message_reads"
_INSTAGRAM_SUBSCRIBED_FIELDS = "messages"


class WebhookRegistrarFactory:
    """Builds the channel_type -> WebhookRegistrarPort map used by
    CreateChannelConnectionUseCase to auto-register a webhook right
    after creating a channel_connection, for channels that support it.

    Channels without an entry here simply keep the manual/curl flow —
    adding a new one is a one-line addition, no changes needed to the
    use cases themselves.
    """

    def build_all(self) -> Dict[str, WebhookRegistrarPort]:
        """Instantiate every supported webhook registrar.

        Returns:
            Dict[str, WebhookRegistrarPort]: A dict mapping each
            supported channel_type to its registrar.
        """
        return {
            "telegram": TelegramWebhookRegistrar(),
            "facebook": MetaWebhookRegistrar(
                channel="facebook", subscribed_fields=_FACEBOOK_SUBSCRIBED_FIELDS
            ),
            "instagram": MetaWebhookRegistrar(
                channel="instagram", subscribed_fields=_INSTAGRAM_SUBSCRIBED_FIELDS
            ),
        }
