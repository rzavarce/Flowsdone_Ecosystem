"""Port for translating a voice provider's wire protocol (webhook
signature scheme, call-control markup, streaming frame format) to and
from this application's provider-agnostic domain concepts.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Protocol

from app.domain.models.voice_relay_event import VoiceRelayEvent


class VoiceProviderPort(Protocol):
    """Strategy for a single voice provider (Twilio today; any future
    provider implements this same port without the rest of the voice
    module changing - inbound routers, the Kafka worker, and the
    channel sender all depend on this interface, never on a concrete
    vendor SDK.
    """

    provider_name: str

    def verify_webhook_signature(
        self,
        *,
        url: str,
        form_params: Mapping[str, str],
        signature: str,
        auth_token: str,
    ) -> bool:
        """Verify the signature of an incoming call-control webhook.

        Args:
            url (str): Full, externally-visible URL the provider called.
            form_params (Mapping[str, str]): Form-encoded POST body,
                as received.
            signature (str): Value of the provider's signature header.
            auth_token (str): Shared secret used to compute the
                expected signature.

        Returns:
            bool: True if the signature is present and valid.
        """
        ...

    def build_twiml_connect(
        self,
        *,
        stream_url: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        tts_provider: Optional[str] = None,
        tts_language: Optional[str] = None,
        transcription_language: Optional[str] = None,
        transcription_provider: Optional[str] = None,
        speech_model: Optional[str] = None,
        action_url: Optional[str] = None,
        welcome_greeting: Optional[str] = None,
    ) -> str:
        """Build the call-control markup that connects the call to our
        real-time streaming WebSocket endpoint.

        Args:
            stream_url (str): The wss:// URL the provider should open
                a streaming connection to.
            voice (Optional[str]): TTS voice to speak the agent's
                responses with (provider-specific catalog). None uses
                the provider's own default.
            language (Optional[str]): BCP-47 language for STT/TTS
                (e.g. "es-MX"). None uses the provider's own default.
            tts_provider (Optional[str]): Which TTS engine to use, if
                the voice provider supports more than one. None uses
                the provider's own default.
            tts_language (Optional[str]): BCP-47 language for
                text-to-speech only, independent of `language`
                (e.g. "es-MX", or "multi" for automatic per-response
                language detection - only supported by some TTS
                providers, e.g. ElevenLabs; see README section 18).
                None uses the provider's own default.
            transcription_language (Optional[str]): BCP-47 language for
                speech-to-text only (e.g. "es-MX", or "multi" for
                automatic language detection - only supported by some
                transcription providers, e.g. Deepgram). None uses the
                provider's own default (which may not match the
                caller's language - see README section 18).
            transcription_provider (Optional[str]): Which STT engine to
                use, if the voice provider supports more than one.
            speech_model (Optional[str]): Provider-specific STT model
                name.
            action_url (Optional[str]): If given, the URL the provider
                calls with fresh call-control instructions once the
                streaming session ends (human handoff/transfer). None
                skips this - the call just ends when the session does.
            welcome_greeting (Optional[str]): Sentence the provider
                speaks automatically as soon as the session connects,
                before the caller says anything. None leaves the
                caller to speak first (the provider's own default).

        Returns:
            str: The response body to return to the provider's webhook
            (e.g. TwiML XML for Twilio).
        """
        ...

    def parse_relay_frame(self, raw: Dict[str, Any]) -> VoiceRelayEvent:
        """Normalize one frame received on the streaming WebSocket.

        Args:
            raw (Dict[str, Any]): The raw, provider-specific JSON frame.

        Returns:
            VoiceRelayEvent: The normalized, provider-agnostic event.
        """
        ...

    def build_relay_text_frame(
        self, *, text: str, last: bool = True, lang: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build the outbound WebSocket frame that makes the provider
        speak `text` back to the caller.

        Args:
            text (str): Text for the provider to synthesize as speech.
            last (bool): Whether this is the final chunk of the
                response (providers that support incremental token
                streaming use this to know when to start speaking).
            lang (Optional[str]): Per-message language override (e.g.
                "multi" to have a provider that supports it, such as
                ElevenLabs, detect this response's language from
                `text` itself). None uses the session's configured
                language.

        Returns:
            Dict[str, Any]: The frame to send on the streaming
            WebSocket, in the provider's wire format.
        """
        ...

    def build_relay_end_frame(self, *, handoff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the outbound WebSocket frame that ends the streaming
        session and hands the call back to call-control (e.g. for a
        human transfer via the webhook's `action_url`).

        Args:
            handoff_data (Dict[str, Any]): Arbitrary data to carry over
                to the call-control webhook that runs next (e.g. which
                phone number to dial).

        Returns:
            Dict[str, Any]: The frame to send on the streaming
            WebSocket, in the provider's wire format.
        """
        ...

    def build_handoff_twiml(self, *, phone_number: str, caller_id: Optional[str] = None) -> str:
        """Build the call-control markup that transfers the call to a
        human agent's phone number.

        Args:
            phone_number (str): Phone number to dial/bridge the call to.
            caller_id (Optional[str]): Caller id to present on the
                outbound leg. Required by some providers when the
                original call did not come from a real phone number
                (e.g. a browser softphone) - see README section 18.

        Returns:
            str: The response body to return to the provider's
            call-control webhook (e.g. TwiML `<Dial>` for Twilio).
        """
        ...
