"""Tests for AcceptIncomingCallUseCase: routing a call to its voice channel."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.application.use_cases.accept_incoming_call import AcceptIncomingCallUseCase
from api_gateway.tests.support.fakes import FakeCallSessionRepo, FakeChannelConnectionRepo, make_channel_resolution

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)


def _use_case(resolution):
    sessions = FakeCallSessionRepo()
    use_case = AcceptIncomingCallUseCase(
        channel_connections=FakeChannelConnectionRepo(resolution=resolution),
        call_sessions=sessions,
        session_ttl_seconds=3600,
        provider="twilio",
    )
    return use_case, sessions


async def test_a_call_to_a_voice_channel_opens_its_session_with_the_channel_settings():
    resolution = make_channel_resolution(channel_type="voice", config={"welcome_greeting": "Hola"})
    use_case, sessions = _use_case(resolution)

    session = await use_case.execute(to_number="+34911000000", from_number="client:demo-1890on91", call_sid="CA1", now=NOW)

    assert sessions.sessions["CA1"] is session
    assert (session.status, session.provider, session.started_at) == ("ringing", "twilio", NOW)
    assert session.agent_id == resolution.agent_id and session.config == {"welcome_greeting": "Hola"}
    assert session.from_number == "client:demo-1890on91"


async def test_a_number_without_a_voice_channel_is_not_accepted():
    use_case, sessions = _use_case(None)

    assert await use_case.execute(to_number="+34911000000", from_number="+34600", call_sid="CA2", now=NOW) is None
    assert sessions.sessions == {}
