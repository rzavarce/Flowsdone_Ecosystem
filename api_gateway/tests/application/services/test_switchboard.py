"""Tests for Switchboard: session resolution/creation, delegation to
the current app's connector, history recording, and switch_app().
"""

from __future__ import annotations

import pytest

from api_gateway.app.application.services.switchboard import (
    ChannelMessageNotRoutable,
    Switchboard,
    build_conversation_id,
)
from api_gateway.app.domain.ports.outbound.app_connector import AppTurnResult
from api_gateway.tests.support.fakes import (
    FakeAppConnector,
    FakeChannelConnectionRepo,
    FakeOutboundHandler,
    FakeSessionHistoryRepository,
    FakeSessionRepository,
    make_channel_resolution,
    make_session,
)

pytestmark = pytest.mark.anyio


def _switchboard(
    *,
    resolution=None,
    session=None,
    connectors=None,
    session_ttl_seconds: int = 86400,
):
    channel_connection_repo = FakeChannelConnectionRepo(resolution=resolution)
    session_repo = FakeSessionRepository(session=session)
    session_history_repo = FakeSessionHistoryRepository()
    outbound_handler = FakeOutboundHandler()
    app_connectors = connectors if connectors is not None else {"langflow": FakeAppConnector()}

    switchboard = Switchboard(
        channel_connection_repo=channel_connection_repo,
        session_repo=session_repo,
        session_history_repo=session_history_repo,
        app_connectors=app_connectors,
        outbound_handler=outbound_handler,
        session_ttl_seconds=session_ttl_seconds,
    )
    return switchboard, session_repo, session_history_repo, outbound_handler, app_connectors


# --- handle_inbound_turn(): new session -----------------------------------


async def test_creates_a_new_session_and_delegates_to_the_default_app():
    resolution = make_channel_resolution(
        channel_type="telegram", external_id="bot-1", langflow_flow_id="flow-abc"
    )
    connector = FakeAppConnector()
    switchboard, session_repo, session_history_repo, _, _ = _switchboard(
        resolution=resolution, connectors={"langflow": connector}
    )

    await switchboard.handle_inbound_turn(
        channel_type="telegram",
        external_id="bot-1",
        external_conversation_key="chat-42",
        sender_id="user-7",
        message_text="hola",
        raw_payload={"raw": True},
    )

    expected_session_id = build_conversation_id(resolution.project_id, "telegram", "chat-42")
    session = session_repo.sessions[expected_session_id]
    assert session.current_app == "langflow"
    assert session.channel_connection_id == resolution.channel_connection_id
    assert session.variables["langflow_flow_id"] == "flow-abc"
    assert session.last_messages[-1].direction == "inbound"
    assert session.last_messages[-1].text == "hola"

    assert len(connector.calls) == 1
    assert connector.calls[0]["message_text"] == "hola"
    assert connector.calls[0]["session"].id == expected_session_id

    assert session_history_repo.events == [
        {
            "session_id": expected_session_id,
            "project_id": resolution.project_id,
            "event_type": "started",
            "from_app": None,
            "to_app": "langflow",
            "reason": None,
        }
    ]
    assert session_history_repo.messages == [
        {
            "session_id": expected_session_id,
            "project_id": resolution.project_id,
            "direction": "inbound",
            "text": "hola",
            "app": "langflow",
        }
    ]


async def test_no_matching_channel_connection_raises_not_routable():
    switchboard, _, _, _, _ = _switchboard(resolution=None)

    with pytest.raises(ChannelMessageNotRoutable):
        await switchboard.handle_inbound_turn(
            channel_type="telegram",
            external_id="unknown-bot",
            external_conversation_key="chat-1",
            sender_id="user-1",
            message_text="hola",
            raw_payload={},
        )


async def test_unregistered_current_app_raises_not_routable():
    resolution = make_channel_resolution(channel_type="telegram", external_id="bot-1")
    existing_session = make_session(
        id=build_conversation_id(resolution.project_id, "telegram", "chat-42"),
        current_app="zendesk",
    )
    switchboard, _, _, _, _ = _switchboard(
        resolution=resolution, session=existing_session, connectors={"langflow": FakeAppConnector()}
    )

    with pytest.raises(ChannelMessageNotRoutable):
        await switchboard.handle_inbound_turn(
            channel_type="telegram",
            external_id="bot-1",
            external_conversation_key="chat-42",
            sender_id="user-1",
            message_text="hola",
            raw_payload={},
        )


# --- handle_inbound_turn(): existing session -------------------------------


async def test_reuses_an_existing_session_without_re_resolving_the_flow_id():
    resolution = make_channel_resolution(
        channel_type="telegram", external_id="bot-1", langflow_flow_id="flow-NEW"
    )
    existing_session = make_session(
        id=build_conversation_id(resolution.project_id, "telegram", "chat-42"),
        current_app="langflow",
        variables={"langflow_flow_id": "flow-ORIGINAL"},
    )
    connector = FakeAppConnector()
    switchboard, session_repo, session_history_repo, _, _ = _switchboard(
        resolution=resolution, session=existing_session, connectors={"langflow": connector}
    )

    await switchboard.handle_inbound_turn(
        channel_type="telegram",
        external_id="bot-1",
        external_conversation_key="chat-42",
        sender_id="user-1",
        message_text="segundo turno",
        raw_payload={},
    )

    saved = session_repo.sessions[existing_session.id]
    # The flow id is snapshotted once at creation - a later change to
    # the agent's configured flow must not silently redirect an
    # in-progress conversation.
    assert saved.variables["langflow_flow_id"] == "flow-ORIGINAL"
    # No "started" event for a session that already existed.
    assert session_history_repo.events == []
    assert len(connector.calls) == 1


# --- handle_inbound_turn(): synchronous connector result -------------------


async def test_delivers_immediately_when_the_connector_returns_a_result():
    resolution = make_channel_resolution(channel_type="telegram", external_id="bot-1")
    connector = FakeAppConnector(result=AppTurnResult(text="ticket creado"))
    switchboard, _, _, outbound_handler, _ = _switchboard(
        resolution=resolution, connectors={"langflow": connector}
    )

    await switchboard.handle_inbound_turn(
        channel_type="telegram",
        external_id="bot-1",
        external_conversation_key="chat-42",
        sender_id="user-1",
        message_text="hola",
        raw_payload={},
    )

    assert len(outbound_handler.delivered) == 1
    envelope = outbound_handler.delivered[0]
    assert envelope.payload["message"] == "ticket creado"
    assert envelope.channel == "telegram"


async def test_does_not_deliver_when_connector_returns_none():
    resolution = make_channel_resolution(channel_type="telegram", external_id="bot-1")
    connector = FakeAppConnector(result=None)
    switchboard, _, _, outbound_handler, _ = _switchboard(
        resolution=resolution, connectors={"langflow": connector}
    )

    await switchboard.handle_inbound_turn(
        channel_type="telegram",
        external_id="bot-1",
        external_conversation_key="chat-42",
        sender_id="user-1",
        message_text="hola",
        raw_payload={},
    )

    assert outbound_handler.delivered == []


# --- switch_app() ------------------------------------------------------------


async def test_switch_app_updates_current_app_persists_and_logs_event():
    session = make_session(current_app="langflow")
    switchboard, session_repo, session_history_repo, _, _ = _switchboard(
        session=session, connectors={"langflow": FakeAppConnector(), "zendesk": FakeAppConnector()}
    )

    updated = await switchboard.switch_app(session_id=session.id, to_app="zendesk", reason="escalation")

    assert updated.current_app == "zendesk"
    assert session_repo.sessions[session.id].current_app == "zendesk"
    assert session_history_repo.events == [
        {
            "session_id": session.id,
            "project_id": session.project_id,
            "event_type": "app_switched",
            "from_app": "langflow",
            "to_app": "zendesk",
            "reason": "escalation",
        }
    ]


async def test_switch_app_rejects_an_unknown_app():
    session = make_session(current_app="langflow")
    switchboard, _, _, _, _ = _switchboard(session=session, connectors={"langflow": FakeAppConnector()})

    with pytest.raises(ValueError):
        await switchboard.switch_app(session_id=session.id, to_app="not-registered")


async def test_switch_app_raises_not_routable_when_session_does_not_exist():
    switchboard, _, _, _, _ = _switchboard(
        session=None, connectors={"langflow": FakeAppConnector(), "zendesk": FakeAppConnector()}
    )

    with pytest.raises(ChannelMessageNotRoutable):
        await switchboard.switch_app(session_id="missing-session", to_app="zendesk")
