"""Canonical, provider-agnostic voice streaming event."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

VoiceRelayEventType = Literal["setup", "prompt", "interrupt", "dtmf", "end"]


class VoiceRelayEvent(BaseModel):
    """A single frame of a real-time voice streaming session, normalized
    from a provider's wire format (e.g. Twilio ConversationRelay).

    Keeping this provider-agnostic lets the inbound WebSocket handler
    depend only on VoiceProviderPort.parse_relay_frame() instead of a
    specific vendor's JSON shape.

    Attributes:
        type (VoiceRelayEventType): Kind of event.
        call_sid (str): Provider-assigned unique id for the call.
        text (Optional[str]): Transcribed caller speech (type="prompt")
            or DTMF digits (type="dtmf"); unset for other event types.
        raw (Dict[str, Any]): The original, unparsed provider frame,
            kept for debugging and payload logging.
    """

    type: VoiceRelayEventType
    call_sid: str
    text: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
