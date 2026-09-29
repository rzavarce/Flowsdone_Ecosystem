"""Tests for the web chat WebSocket (/ws): tenant channel key and demo test token."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import anyio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.adapters.inbound.http.websocket import TEST_TOKEN_EXPIRED_CLOSE_CODE, router
from app.application.services.switchboard import ChannelMessageNotRoutable, build_conversation_id
from app.application.services.webchat import TestTokenClaims, sign_test_token
from app.application.services.ws_registry import WSRegistry
from app.core.config import settings
from app.application.use_cases.webchat_share import ManageWebchatShareLinksUseCase
from app.domain.models.agent import Agent
from api_gateway.tests.support.fakes import FakeLoginThrottle, FakeWebchatShareLinkRepo, make_channel_resolution

KEY = "wc_" + "a" * 32


class FakeChannels:
    def __init__(self, resolution=None):
        self.resolution = resolution

    async def get_by_channel_and_external_id(self, channel_type, external_id):
        if self.resolution and channel_type == "webchat" and external_id == KEY:
            return self.resolution
        return None


class FakeSwitchboard:
    def __init__(self, error: Exception | None = None):
        self.turns: List[Dict[str, Any]] = []
        self.error = error

    async def handle_inbound_turn(self, **kwargs):
        if self.error:
            raise self.error
        self.turns.append(kwargs)


class FakeIngest:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)


class FakeDemoRecorder:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def record_inbound(self, **kwargs):
        self.calls.append(kwargs)


class FakeAgents:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.agent = Agent(id=uuid4(), project_id=uuid4(), name="Asistente", langflow_flow_id="flow-share",
                           created_at=now, updated_at=now)

    async def get_by_id(self, agent_id):
        return self.agent if agent_id == self.agent.id else None


def _world(origins=None, switchboard=None):
    resolution = make_channel_resolution(channel_type="webchat", config={"allowed_origins": origins or []})
    app = FastAPI()
    app.include_router(router)
    agents = FakeAgents()
    state = dict(
        channel_connection_repo=FakeChannels(resolution), ws_registry=WSRegistry(),
        switchboard=switchboard or FakeSwitchboard(), ingest_message_use_case=FakeIngest(),
        login_throttle=FakeLoginThrottle(),
        webchat_share_use_case=ManageWebchatShareLinksUseCase(
            links=FakeWebchatShareLinkRepo(), agents=agents, demo_url="https://chat.test/"
        ),
        agents=agents,
        demo_conversation_recorder=FakeDemoRecorder(),
    )
    for name, value in state.items():
        setattr(app.state, name, value)
    return TestClient(app), state, resolution


def _message(text, visitor="visitor-1"):
    return {"type": "chat.message", "conversation_id": visitor, "payload": {"message": text}}


def _token(**over):
    claims = dict(agent_id="agent-9", workflow_id="flow-9", expires_at=int(time.time()) + 600)
    claims.update(over)
    return sign_test_token(TestTokenClaims(**claims), settings.CALLBACK_HMAC_SECRET)


@pytest.mark.parametrize("query", ["", "?key=wc_unknown", "?test_token=forged.token", f"?test_token={'x'}"])
def test_connections_without_a_valid_key_or_token_are_refused(query):
    client, _, _ = _world()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws{query}") as ws:
            ws.receive_json()


def test_a_channel_message_goes_through_the_switchboard_as_a_webchat_turn():
    client, state, resolution = _world()
    with client.websocket_connect(f"/ws?key={KEY}", headers={"origin": "https://any.example"}) as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json() == {"type": "connected", "conversation_id": "visitor-1"}
        assert ws.receive_json()["type"] == "accepted"
        session_id = build_conversation_id(resolution.project_id, "webchat", "visitor-1")
        assert session_id in state["ws_registry"]._connections  # replies find their way back
    [turn] = state["switchboard"].turns
    assert (turn["channel_type"], turn["external_id"], turn["external_conversation_key"], turn["message_text"]) == (
        "webchat", KEY, "visitor-1", "Hola")
    assert state["ingest_message_use_case"].calls == []


def test_allowed_origins_are_enforced():
    client, _, _ = _world(origins=["https://cliente.es"])
    with client.websocket_connect(f"/ws?key={KEY}", headers={"origin": "https://cliente.es"}) as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json()["type"] == "connected"
    for origin in ({"origin": "https://otro.com"}, {}):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws?key={KEY}", headers=origin) as ws:
                ws.receive_json()


def test_each_visitor_ip_is_rate_limited_and_long_messages_are_refused(monkeypatch):
    monkeypatch.setattr(settings, "WEBCHAT_MAX_MESSAGES_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "WEBCHAT_MAX_MESSAGE_CHARS", 10)
    client, state, _ = _world()
    with client.websocket_connect(f"/ws?key={KEY}") as ws:
        ws.send_json(_message("uno"))
        assert [ws.receive_json()["type"] for _ in range(2)] == ["connected", "accepted"]
        ws.send_json(_message("dos"))
        assert ws.receive_json()["type"] == "accepted"
        ws.send_json(_message("tres"))
        assert ws.receive_json() == {"type": "chat.error", "error": "rate_limited"}
        ws.send_json(_message("x" * 11))
        assert ws.receive_json() == {"type": "chat.error", "error": "message_too_long"}
    assert len(state["switchboard"].turns) == 2


def test_a_channel_that_stops_being_routable_is_reported():
    client, _, _ = _world(switchboard=FakeSwitchboard(ChannelMessageNotRoutable("gone")))
    with client.websocket_connect(f"/ws?key={KEY}") as ws:
        ws.send_json(_message("Hola"))
        ws.receive_json()
        assert ws.receive_json() == {"type": "chat.error", "error": "channel_unavailable"}


def test_an_invalid_visitor_id_is_refused():
    client, _, _ = _world()
    with client.websocket_connect(f"/ws?key={KEY}") as ws:
        ws.send_json(_message("Hola", visitor="<script>"))
        assert ws.receive_json() == {"type": "chat.error", "error": "missing_conversation_id"}


def test_the_demo_goes_straight_to_the_tested_agent_and_is_not_a_channel_turn():
    client, state, _ = _world()
    with client.websocket_connect(f"/ws?test_token={_token()}") as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json()["type"] == "connected"
        assert ws.receive_json()["type"] == "accepted"
    [call] = state["ingest_message_use_case"].calls
    assert call["workflow_id"] == "flow-9" and call["conversation_id"] == "test:agent-9:visitor-1"
    assert call["channel"] == "webchat-test" and call["payload"]["message"] == "Hola"
    assert state["switchboard"].turns == []


def test_an_expired_test_token_is_told_so_and_closed_with_the_no_retry_code():
    """A genuine but expired demo link gets an explicit error (the widget
    shows it and stops reconnecting) instead of a silent refusal."""
    client, state, _ = _world()
    with client.websocket_connect(f"/ws?test_token={_token(expires_at=int(time.time()) - 1)}") as ws:
        assert ws.receive_json() == {"type": "chat.error", "error": "test_token_expired"}
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == TEST_TOKEN_EXPIRED_CLOSE_CODE == 4001
    assert state["ingest_message_use_case"].calls == []


def test_a_forged_token_is_refused_silently_even_if_it_looks_expired():
    """Only tokens this gateway signed get the "expired" explanation."""
    genuine = _token(expires_at=int(time.time()) - 1)
    payload, _ = genuine.split(".")
    client, _, _ = _world()
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"/ws?test_token={payload}.forgedsignature") as ws:
            ws.receive_json()
    assert refused.value.code == 1008



def _share(state, **create):
    """Create a share link for the world's agent; returns (token, link id)."""
    use_case = state["webchat_share_use_case"]
    shared = anyio.run(lambda: use_case.create(state["agents"].agent, created_by=None, expires_in_days=None, **create))
    return parse_qs(urlsplit(shared.url).query)["share"][0], shared.link.id


def test_a_share_link_goes_straight_to_the_agents_flow_on_its_own_channel():
    client, state, _ = _world()
    token, share_id = _share(state)
    with client.websocket_connect(f"/ws?share={token}") as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json()["type"] == "connected"
        assert ws.receive_json()["type"] == "accepted"
    [call] = state["ingest_message_use_case"].calls
    assert call["workflow_id"] == "flow-share"
    assert call["conversation_id"] == f"share:{share_id}:visitor-1"
    assert call["channel"] == "webchat-share" and call["sender_id"] == "share:visitor-1"
    assert state["switchboard"].turns == []
    [recorded] = state["demo_conversation_recorder"].calls
    assert recorded["session_id"] == f"share:{share_id}:visitor-1" and recorded["share_id"] == share_id
    assert recorded["agent_id"] == state["agents"].agent.id
    assert recorded["project_id"] == state["agents"].agent.project_id
    assert recorded["visitor_id"] == "visitor-1" and recorded["text"] == "Hola"


def test_the_console_demo_is_not_recorded_as_a_conversation():
    client, state, _ = _world()
    with client.websocket_connect(f"/ws?test_token={_token()}") as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json()["type"] == "connected"
        assert ws.receive_json()["type"] == "accepted"
    assert state["demo_conversation_recorder"].calls == []


def test_a_revoked_share_link_is_told_so_and_closed_with_the_no_retry_code():
    client, state, _ = _world()
    token, share_id = _share(state)
    use_case = state["webchat_share_use_case"]
    anyio.run(lambda: use_case.revoke(state["agents"].agent, share_id))
    with client.websocket_connect(f"/ws?share={token}") as ws:
        assert ws.receive_json() == {"type": "chat.error", "error": "share_link_unavailable"}
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == TEST_TOKEN_EXPIRED_CLOSE_CODE
    assert state["ingest_message_use_case"].calls == []


def test_an_unknown_share_token_is_refused_silently():
    client, _, _ = _world()
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/ws?share=made-up-token") as ws:
            ws.receive_json()
    assert refused.value.code == 1008


def test_revoking_a_share_link_cuts_a_chat_already_open():
    client, state, _ = _world()
    token, share_id = _share(state)
    use_case = state["webchat_share_use_case"]
    with client.websocket_connect(f"/ws?share={token}") as ws:
        ws.send_json(_message("Hola"))
        assert ws.receive_json()["type"] == "connected"
        assert ws.receive_json()["type"] == "accepted"
        anyio.run(lambda: use_case.revoke(state["agents"].agent, share_id))
        ws.send_json(_message("¿Sigues ahí?"))
        assert ws.receive_json() == {"type": "chat.error", "error": "share_link_unavailable"}
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == TEST_TOKEN_EXPIRED_CLOSE_CODE
    assert len(state["ingest_message_use_case"].calls) == 1
