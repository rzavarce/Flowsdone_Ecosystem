"""Twilio implementation of VoiceProviderPort.

Confines every Twilio-specific detail (ConversationRelay's wire
format, the TwiML call-control markup, the X-Twilio-Signature scheme)
to this single adapter. The domain and application layers, and the
voice inbound routers/worker, only ever depend on VoiceProviderPort.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Mapping, Optional

from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.domain.models.voice_relay_event import VoiceRelayEvent
from app.domain.ports.outbound import VoiceProviderPort

logger = logging.getLogger("channels.voice.twilio_provider")

_FRAME_TYPES_WITHOUT_TEXT = ("setup", "interrupt", "end")


class TwilioVoiceProviderAdapter(VoiceProviderPort):
    """Translates between Twilio's ConversationRelay/TwiML wire format
    and this application's provider-agnostic voice domain concepts.
    """

    provider_name = "twilio"

    def verify_webhook_signature(
        self,
        *,
        url: str,
        form_params: Mapping[str, str],
        signature: str,
        auth_token: str,
    ) -> bool:
        """Verify Twilio's X-Twilio-Signature header.

        Args:
            url (str): Full, externally-visible URL Twilio called.
            form_params (Mapping[str, str]): Form-encoded POST body,
                as received.
            signature (str): Value of the X-Twilio-Signature header.
            auth_token (str): The Twilio account's Auth Token.

        Returns:
            bool: True if the signature is present and valid.
        """
        if not signature or not auth_token:
            return False
        return RequestValidator(auth_token).validate(url, dict(form_params), signature)

    def build_twiml_connect(
        self,
        *,
        stream_url: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        tts_provider: Optional[str] = None,
        transcription_language: Optional[str] = None,
        transcription_provider: Optional[str] = None,
        speech_model: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> str:
        """Build the TwiML that connects the call to our ConversationRelay
        streaming WebSocket endpoint.

        Args:
            stream_url (str): The wss:// URL Twilio should open a
                ConversationRelay connection to.
            voice (Optional[str]): Twilio TTS voice name (e.g.
                "Polly.Mia-Neural"). None uses Twilio's default.
            language (Optional[str]): BCP-47 language for STT/TTS
                (e.g. "es-MX"). None uses Twilio's default.

                Twilio error 64101 if set without also wiring
                transcription_provider/speech_model: ConversationRelay
                treats the combined `language` attribute as an
                all-or-nothing set (TTS *and* STT config together) -
                do not set this unless transcription config is also
                supplied, or Twilio rejects the call outright. Prefer
                `transcription_language` (STT only) or `voice` +
                `tts_provider` (TTS only) instead of this combined one.
            tts_provider (Optional[str]): Twilio TTS engine (e.g.
                "Google", "ElevenLabs", "Amazon"). None uses Twilio's
                default.
            transcription_language (Optional[str]): BCP-47 language for
                speech-to-text only (e.g. "es-MX"). Twilio's own
                default is en-US regardless of what language the agent
                replies in - see README section 18.
            transcription_provider (Optional[str]): Twilio STT engine
                (e.g. "Google", "Deepgram"). None uses Twilio's default.
            speech_model (Optional[str]): Twilio STT model name.
            action_url (Optional[str]): If given, Twilio calls this URL
                with fresh TwiML once the ConversationRelay session
                ends (e.g. after we send an "end" frame with
                handoffData for a human transfer). None omits the
                `action` attribute - the call just ends with the
                session.

        Returns:
            str: The TwiML XML document to return to Twilio's webhook.
        """
        response = VoiceResponse()
        connect = Connect(action=action_url, method="POST") if action_url else Connect()
        connect.conversation_relay(
            url=stream_url,
            voice=voice,
            language=language,
            tts_provider=tts_provider,
            transcription_language=transcription_language,
            transcription_provider=transcription_provider,
            speech_model=speech_model,
        )
        response.append(connect)
        return str(response)

    def parse_relay_frame(self, raw: Dict[str, Any]) -> VoiceRelayEvent:
        """Normalize one ConversationRelay WebSocket frame.

        Args:
            raw (Dict[str, Any]): The raw JSON frame, as sent by
                Twilio (setup/prompt/interrupt/dtmf/end).

        Returns:
            VoiceRelayEvent: The normalized, provider-agnostic event.

        Raises:
            ValueError: If `raw` has no recognized ConversationRelay
                frame type.
        """
        frame_type = raw.get("type")
        call_sid = raw.get("callSid", "")

        if frame_type in _FRAME_TYPES_WITHOUT_TEXT:
            return VoiceRelayEvent(type=frame_type, call_sid=call_sid, raw=raw)

        if frame_type == "prompt":
            return VoiceRelayEvent(
                type="prompt", call_sid=call_sid, text=raw.get("voicePrompt"), raw=raw
            )

        if frame_type == "dtmf":
            return VoiceRelayEvent(type="dtmf", call_sid=call_sid, text=raw.get("digit"), raw=raw)

        logger.warning("channels.voice.twilio.unknown_frame_type", extra={"type": frame_type})
        raise ValueError(f"unsupported ConversationRelay frame type: {frame_type!r}")

    def build_relay_text_frame(self, *, text: str, last: bool = True) -> Dict[str, Any]:
        """Build the ConversationRelay "text" frame that makes Twilio
        speak `text` to the caller.

        Args:
            text (str): Text for Twilio to synthesize as speech.
            last (bool): Whether this is the final chunk of the
                response.

        Returns:
            Dict[str, Any]: The frame to send on the ConversationRelay
            WebSocket.
        """
        return {"type": "text", "token": text, "last": last}

    def build_relay_end_frame(self, *, handoff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the ConversationRelay "end" frame that hands the call
        back to call-control (e.g. the webhook's `action_url`).

        Args:
            handoff_data (Dict[str, Any]): Arbitrary data to carry
                over; Twilio requires `handoffData` as a string, so
                this is JSON-encoded.

        Returns:
            Dict[str, Any]: The frame to send on the ConversationRelay
            WebSocket.
        """
        return {"type": "end", "handoffData": json.dumps(handoff_data)}

    def build_handoff_twiml(self, *, phone_number: str, caller_id: Optional[str] = None) -> str:
        """Build the TwiML that dials/bridges the call to a human agent.

        Args:
            phone_number (str): Phone number to dial.
            caller_id (Optional[str]): Caller id for the outbound leg.
                Twilio requires this (error 13214) when the original
                call came from a TwilioClient/SIP leg rather than a
                real phone number - e.g. the browser softphone demo.

        Returns:
            str: The TwiML XML document to return to Twilio's
            `action_url` webhook.
        """
        response = VoiceResponse()
        response.dial(phone_number, caller_id=caller_id)
        return str(response)
