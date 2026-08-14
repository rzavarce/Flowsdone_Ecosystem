"""Tests for TwilioVoiceSender."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from api_gateway.app.adapters.outbound.channels.twilio_voice_sender import TwilioVoiceSender

pytestmark = pytest.mark.anyio


class FakeCallSessionRegistry:
    """Minimal stand-in for WSRegistry, only what TwilioVoiceSender uses."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send(self, call_sid: str, message: dict) -> None:
        self.sent.append({"call_sid": call_sid, "message": message})


class FakeVoiceProvider:
    """Minimal stand-in for VoiceProviderPort, only what the sender uses."""

    def build_relay_text_frame(self, *, text: str, last: bool = True) -> Dict[str, Any]:
        return {"type": "text", "token": text, "last": last}


async def test_send_pushes_a_relay_frame_to_the_calls_registry():
    registry = FakeCallSessionRegistry()
    sender = TwilioVoiceSender(call_session_registry=registry, voice_provider=FakeVoiceProvider())

    await sender.send(
        external_id="+15559998888", recipient_id="CA123", text="hola", credentials={}
    )

    assert registry.sent == [
        {"call_sid": "CA123", "message": {"type": "text", "token": "hola", "last": True}}
    ]


async def test_send_is_a_noop_when_not_configured():
    sender = TwilioVoiceSender()

    # Should not raise, even with no registry/provider wired.
    await sender.send(external_id="+1555", recipient_id="CA123", text="hola", credentials={})
