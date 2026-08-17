"""End-to-end (in-process WebSocket) tests for the voice streaming endpoint."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_gateway.app.adapters.inbound.http.voice.stream import (
    _matches_human_transfer_phrase,
    router,
)
from api_gateway.app.application.services.ws_registry import WSRegistry
from api_gateway.tests.support.fakes import (
    FakeCallSessionRepo,
    FakeSwitchboard,
    FakeVoiceProvider,
    make_call_session,
)


@pytest.mark.parametrize(
    "text,phrases,expected",
    [
        ("quiero hablar con una persona", ["hablar con una persona"], True),
        ("QUIERO HABLAR CON UNA PERSONA, POR FAVOR", ["hablar con una persona"], True),
        ("dame el precio del producto", ["hablar con una persona", "agente humano"], False),
        ("necesito un agente humano ya", ["hablar con una persona", "agente humano"], True),
        ("hola", [], False),
        ("hola", [""], False),
    ],
)
def test_matches_human_transfer_phrase(text, phrases, expected):
    assert _matches_human_transfer_phrase(text, phrases) is expected


def _client(**state) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    for key, value in state.items():
        setattr(app.state, key, value)
    return TestClient(app)


def test_prompt_frame_routes_the_transcribed_turn_to_the_voice_channel():
    session = make_call_session(call_sid="CA123", to_number="+15559998888", from_number="+15550001111")
    call_session_repo = FakeCallSessionRepo(session=session)
    call_session_registry = WSRegistry()
    voice_provider = FakeVoiceProvider()
    switchboard = FakeSwitchboard()

    client = _client(
        call_session_repo=call_session_repo,
        call_session_registry=call_session_registry,
        voice_provider=voice_provider,
        switchboard=switchboard,
    )

    with client.websocket_connect("/voice/stream/CA123") as ws:
        ws.send_json({"type": "setup", "callSid": "CA123"})
        ws.send_json({"type": "prompt", "callSid": "CA123", "voicePrompt": "hola, quiero soporte"})
        ws.send_json({"type": "end", "callSid": "CA123"})

    assert len(switchboard.calls) == 1
    call = switchboard.calls[0]
    assert call["channel_type"] == "voice"
    assert call["external_id"] == "+15559998888"
    assert call["external_conversation_key"] == "CA123"
    assert call["sender_id"] == "+15550001111"
    assert call["message_text"] == "hola, quiero soporte"
    # The connection is unregistered and the session cleaned up once the
    # call ends, so a stray outbound response can no longer reach it.
    assert call_session_repo.deleted == ["CA123"]


def test_phrase_match_triggers_handoff_instead_of_routing_to_langflow():
    session = make_call_session(
        call_sid="CA123",
        to_number="+15559998888",
        from_number="+15550001111",
        config={
            "human_transfer_number": "+34601491522",
            "human_transfer_phrases": ["hablar con una persona", "agente humano"],
        },
    )
    call_session_repo = FakeCallSessionRepo(session=session)
    call_session_registry = WSRegistry()
    voice_provider = FakeVoiceProvider()
    switchboard = FakeSwitchboard()

    client = _client(
        call_session_repo=call_session_repo,
        call_session_registry=call_session_registry,
        voice_provider=voice_provider,
        switchboard=switchboard,
    )

    with client.websocket_connect("/voice/stream/CA123") as ws:
        ws.send_json({"type": "setup", "callSid": "CA123"})
        ws.send_json(
            {"type": "prompt", "callSid": "CA123", "voicePrompt": "quiero hablar con una persona"}
        )
        received = ws.receive_json()

    # No Langflow turn - the deterministic trigger short-circuits routing.
    assert switchboard.calls == []
    assert received["type"] == "end"
    handoff_data = json.loads(received["handoffData"])
    assert handoff_data == {
        "reason": "human_transfer",
        "transfer_number": "+34601491522",
        "caller_id": "+15559998888",
    }


def test_non_matching_prompt_still_routes_normally_when_transfer_is_configured():
    session = make_call_session(
        call_sid="CA123",
        to_number="+15559998888",
        from_number="+15550001111",
        config={
            "human_transfer_number": "+34601491522",
            "human_transfer_phrases": ["hablar con una persona"],
        },
    )
    call_session_repo = FakeCallSessionRepo(session=session)
    call_session_registry = WSRegistry()
    voice_provider = FakeVoiceProvider()
    switchboard = FakeSwitchboard()

    client = _client(
        call_session_repo=call_session_repo,
        call_session_registry=call_session_registry,
        voice_provider=voice_provider,
        switchboard=switchboard,
    )

    with client.websocket_connect("/voice/stream/CA123") as ws:
        ws.send_json({"type": "setup", "callSid": "CA123"})
        ws.send_json({"type": "prompt", "callSid": "CA123", "voicePrompt": "cuanto cuesta el router"})
        ws.send_json({"type": "end", "callSid": "CA123"})

    assert len(switchboard.calls) == 1
    assert switchboard.calls[0]["message_text"] == "cuanto cuesta el router"


def test_unknown_call_sid_closes_the_connection_immediately():
    call_session_repo = FakeCallSessionRepo()
    call_session_registry = WSRegistry()
    voice_provider = FakeVoiceProvider()
    switchboard = FakeSwitchboard()

    client = _client(
        call_session_repo=call_session_repo,
        call_session_registry=call_session_registry,
        voice_provider=voice_provider,
        switchboard=switchboard,
    )

    with pytest.raises(Exception):
        with client.websocket_connect("/voice/stream/unknown-call") as ws:
            ws.receive_text()

    assert switchboard.calls == []
