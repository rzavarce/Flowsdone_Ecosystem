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
    """
    Arma el mapa channel_type -> ChannelSenderPort usado por
    HandleOutboundResponseUseCase.deliver() para despachar la respuesta
    de un workflow al canal nativo que originó la conversación.
    """

    def build_all(self) -> Dict[str, ChannelSenderPort]:
        return {
            "whatsapp_evolution": WhatsAppEvolutionSender(),
            "facebook": FacebookSender(),
            "instagram": InstagramSender(),
            "telegram": TelegramSender(),
            "twitter": TwitterSender(),
            "tiktok": TikTokSender(),
        }
