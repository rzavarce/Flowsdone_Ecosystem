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

from app.application.services.ws_registry import WSRegistry
from app.domain.ports.outbound import CallSessionRepositoryPort, ChannelSenderPort, VoiceProviderPort

logger = logging.getLogger("channels.voice.sender")

_MULTI_LANGUAGE = "multi"


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
        call_session_repo: Optional[CallSessionRepositoryPort] = None,
    ) -> None:
        """Build the sender.

        Args:
            call_session_registry (Optional[WSRegistry]): Registry of
                live streaming WebSocket connections, keyed by
                call_sid. None only when voice is not wired up (e.g.
                in tests that just enumerate senders).
            voice_provider (Optional[VoiceProviderPort]): Strategy used
                to build the provider-specific outbound frame.
            call_session_repo (Optional[CallSessionRepositoryPort]):
                Used to read the call's `tts_language` config, so a
                connection set up for automatic per-response language
                detection (ElevenLabs' "multi") gets `lang="multi"` on
                every text frame - see README section 18. None skips
                this lookup, so every frame uses the session's
                TwiML-level default language.
        """
        self._call_session_registry = call_session_registry
        self._voice_provider = voice_provider
        self._call_session_repo = call_session_repo

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

        lang = None
        if self._call_session_repo:
            session = await self._call_session_repo.get(recipient_id)
            if session and session.config.get("tts_language") == _MULTI_LANGUAGE:
                lang = _MULTI_LANGUAGE

        frame = self._voice_provider.build_relay_text_frame(text=text, lang=lang)
        await self._call_session_registry.send(recipient_id, frame)

        logger.info("channel.sender.sent", extra={"channel": "voice", "call_sid": recipient_id})
