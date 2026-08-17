"""Voice channel outbound "sender".

Unlike the other ChannelSenderPort implementations (which call an
external platform's REST API), delivering a voice response means
pushing a frame onto the live, in-process streaming WebSocket the
caller is already connected to - so this sender talks to
`call_session_registry` instead of making an HTTP request.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from api_gateway.app.application.services.ws_registry import WSRegistry
from api_gateway.app.domain.ports.outbound import ChannelSenderPort, VoiceProviderPort

logger = logging.getLogger("channels.voice.sender")


class TwilioVoiceSender(ChannelSenderPort):
    """Delivers an agent's text response to a live voice call.

    Reuses the same delivery path as every other channel
    (HandleOutboundResponseUseCase._deliver_to_channel via
    /internal/outbound) without a voice-specific internal endpoint:
    `recipient_id` here is the call_sid, already carried on the
    envelope as `external_conversation_key` by the generic ingestion
    pipeline.
    """

    def __init__(
        self,
        call_session_registry: Optional[WSRegistry] = None,
        voice_provider: Optional[VoiceProviderPort] = None,
    ) -> None:
        """Build the sender.

        Args:
            call_session_registry (Optional[WSRegistry]): Registry of
                live streaming WebSocket connections, keyed by
                call_sid. None only when voice is not wired up (e.g.
                in tests that just enumerate senders).
            voice_provider (Optional[VoiceProviderPort]): Strategy used
                to build the provider-specific outbound frame.
        """
        self._call_session_registry = call_session_registry
        self._voice_provider = voice_provider

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Speak `text` back to the caller on their live call.

        Args:
            external_id (str): Unused; kept for interface consistency
                with ChannelSenderPort (the called phone number is not
                needed to address an already-open WebSocket).
            recipient_id (str): The call_sid of the live call.
            text (str): Message text for the provider to synthesize.
            credentials (Dict[str, Any]): Unused; the streaming
                WebSocket is already authenticated for this call.
        """
        if not self._call_session_registry or not self._voice_provider:
            logger.error(
                "channel.sender.voice.not_configured",
                extra={"call_sid": recipient_id},
            )
            return

        frame = self._voice_provider.build_relay_text_frame(text=text)
        await self._call_session_registry.send(recipient_id, frame)

        logger.info("channel.sender.sent", extra={"channel": "voice", "call_sid": recipient_id})
