"""Factory that assembles all available channel senders."""

from __future__ import annotations

from typing import Dict

from ....domain.ports.outbound import ChannelSenderPort
from .facebook_sender import FacebookSender
from .instagram_sender import InstagramSender
from .telegram_sender import TelegramSender
from .tiktok_sender import TikTokSender
from .twitter_sender import TwitterSender
from .whatsapp_evolution_sender import WhatsAppEvolutionSender


class ChannelSenderFactory:
    """Builds the channel_type -> ChannelSenderPort map used by
    HandleOutboundResponseUseCase.deliver() to dispatch a workflow
    response to the native channel that originated the conversation.
    """

    def build_all(self) -> Dict[str, ChannelSenderPort]:
        """Instantiate every supported channel sender.

        Returns:
            Dict[str, ChannelSenderPort]: A dict mapping each supported
            channel_type to its sender.
        """
        return {
            "whatsapp_evolution": WhatsAppEvolutionSender(),
            "facebook": FacebookSender(),
            "instagram": InstagramSender(),
            "telegram": TelegramSender(),
            "twitter": TwitterSender(),
            "tiktok": TikTokSender(),
        }
