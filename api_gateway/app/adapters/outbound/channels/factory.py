"""Factory that assembles all available channel senders."""

from __future__ import annotations

from typing import Dict, Optional

from app.application.services.ws_registry import WSRegistry
from app.domain.ports.outbound import ChannelSenderPort, VoiceProviderPort
from app.adapters.outbound.channels.facebook_sender import FacebookSender
from app.adapters.outbound.channels.instagram_sender import InstagramSender
from app.adapters.outbound.channels.telegram_sender import TelegramSender
from app.adapters.outbound.channels.tiktok_sender import TikTokSender
from app.adapters.outbound.channels.twilio_voice_sender import TwilioVoiceSender
from app.adapters.outbound.channels.twitter_sender import TwitterSender
from app.adapters.outbound.channels.whatsapp_evolution_sender import WhatsAppEvolutionSender


class ChannelSenderFactory:
    """Builds the channel_type -> ChannelSenderPort map used by
    HandleOutboundResponseUseCase.deliver() to dispatch a workflow
    response to the native channel that originated the conversation.
    """

    def build_all(
        self,
        *,
        call_session_registry: Optional[WSRegistry] = None,
        voice_provider: Optional[VoiceProviderPort] = None,
    ) -> Dict[str, ChannelSenderPort]:
        """Instantiate every supported channel sender.

        Args:
            call_session_registry (Optional[WSRegistry]): Live voice
                call registry, forwarded to TwilioVoiceSender. Only
                needed to actually deliver voice responses; the
                "voice" entry is always present so callers can rely on
                every ChannelType having a sender.
            voice_provider (Optional[VoiceProviderPort]): Voice
                provider strategy, forwarded to TwilioVoiceSender.

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
            "voice": TwilioVoiceSender(
                call_session_registry=call_session_registry, voice_provider=voice_provider
            ),
        }
