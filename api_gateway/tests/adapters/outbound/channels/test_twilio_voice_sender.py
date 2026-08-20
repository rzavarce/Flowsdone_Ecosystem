"""Tests for TwilioVoiceSender."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest

from app.adapters.outbound.channels.twilio_voice_sender import TwilioVoiceSender
from app.domain.models.call_session import CallSession
from api_gateway.tests.support.fakes import FakeCallSessionRepo

pytestmark = pytest.mark.anyio


class FakeCallSessionRegistry:
    """Minimal stand-in for WSRegistry, only what TwilioVoiceSender uses."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send(self, call_sid: str, message: dict) -> None:
        self.sent.append({"call_sid": call_sid, "message": message})


class FakeVoiceProvider:
    """Minimal stand-in for VoiceProviderPort, only what the sender uses."""

    def build_relay_text_frame(
        self, *, text: str, last: bool = True, lang: Optional[str] = None
    ) -> Dict[str, Any]:
        frame: Dict[str, Any] = {"type": "text", "token": text, "last": last}
        if lang:
            frame["lang"] = lang
        return frame


def _call_session(**config: Any) -> CallSession:
    return CallSession(
        call_sid="CA123",
        channel_connection_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        langflow_flow_id="flow-1",
        from_number="+15550001111",
        to_number="+15559998888",
        provider="twilio",
        started_at=datetime.now(timezone.utc),
        config=config,
    )


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


async def test_send_includes_multi_lang_when_the_session_is_configured_for_it():
    registry = FakeCallSessionRegistry()
    call_session_repo = FakeCallSessionRepo(session=_call_session(tts_language="multi"))
    sender = TwilioVoiceSender(
        call_session_registry=registry,
        voice_provider=FakeVoiceProvider(),
        call_session_repo=call_session_repo,
    )

    await sender.send(
        external_id="+15559998888", recipient_id="CA123", text="hola", credentials={}
    )

    assert registry.sent[0]["message"]["lang"] == "multi"


async def test_send_omits_lang_when_the_session_is_not_configured_for_multi_language():
    registry = FakeCallSessionRegistry()
    call_session_repo = FakeCallSessionRepo(session=_call_session(tts_provider="Amazon"))
    sender = TwilioVoiceSender(
        call_session_registry=registry,
        voice_provider=FakeVoiceProvider(),
        call_session_repo=call_session_repo,
    )

    await sender.send(
        external_id="+15559998888", recipient_id="CA123", text="hola", credentials={}
    )

    assert "lang" not in registry.sent[0]["message"]


async def test_send_omits_lang_when_there_is_no_session_for_the_call():
    registry = FakeCallSessionRegistry()
    call_session_repo = FakeCallSessionRepo()
    sender = TwilioVoiceSender(
        call_session_registry=registry,
        voice_provider=FakeVoiceProvider(),
        call_session_repo=call_session_repo,
    )

    await sender.send(
        external_id="+15559998888", recipient_id="CA123", text="hola", credentials={}
    )

    assert "lang" not in registry.sent[0]["message"]
