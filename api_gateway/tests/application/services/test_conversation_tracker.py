"""Tests for ConversationTracker: opening, reusing and rotating a
session's conversation, and recording messages into the event stream.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.conversation_tracker import ConversationTracker
from app.domain.models.conversation import ConversationLifecyclePolicy
from api_gateway.tests.support.fakes import (
    FakeConversationEventPublisher,
    FakeConversationRepository,
    FakeSessionHistoryRepository,
    make_conversation,
    make_session,
)

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
POLICY = ConversationLifecyclePolicy(inactivity=timedelta(hours=24), max_duration=timedelta(days=7))


def _tracker(*conversations):
    repo = FakeConversationRepository(*conversations)
    events = FakeConversationEventPublisher()
    history = FakeSessionHistoryRepository()
    tracker = ConversationTracker(
        conversation_repo=repo, event_publisher=events, session_history_repo=history, policy=POLICY
    )
    return tracker, repo, events, history


async def test_first_inbound_message_opens_a_conversation_and_publishes_it():
    tracker, repo, events, _ = _tracker()
    session = make_session(user_identifier="+34600000000")

    conversation = await tracker.record_inbound(session=session, text="hola", now=T0)

    assert session.conversation_id == conversation.id
    assert conversation.session_id == session.id
    assert conversation.tenant_id == session.tenant_id
    assert conversation.contact == "+34600000000"
    assert conversation.started_at == T0
    assert repo.recorded == [{"conversation_id": conversation.id, "direction": "inbound", "at": T0}]

    [event] = events.events
    assert event.conversation_id == conversation.id
    assert event.direction == "inbound"
    assert event.sender_type == "contact"
    assert event.text == "hola"
    assert event.timestamp == T0
    assert event.session_id == session.id


async def test_inbound_message_within_the_window_reuses_the_conversation():
    session = make_session()
    current = make_conversation(session_id=session.id, started_at=T0, last_inbound_at=T0)
    session.conversation_id = current.id
    tracker, repo, events, history = _tracker(current)

    conversation = await tracker.record_inbound(session=session, text="sigo", now=T0 + timedelta(hours=23))

    assert conversation.id == current.id
    assert session.conversation_id == current.id
    assert len(repo.conversations) == 1
    assert history.events == []


async def test_inbound_message_after_24h_closes_the_old_conversation_and_opens_a_new_one():
    session = make_session()
    old = make_conversation(session_id=session.id, started_at=T0, last_inbound_at=T0)
    session.conversation_id = old.id
    tracker, repo, events, history = _tracker(old)

    conversation = await tracker.record_inbound(session=session, text="volví", now=T0 + timedelta(hours=30))

    assert conversation.id != old.id
    assert session.conversation_id == conversation.id
    closed = repo.conversations[old.id]
    assert closed.status == "closed"
    assert closed.close_reason == "inactivity"
    # Stamped with when it actually expired, not with "now".
    assert closed.closed_at == T0 + timedelta(hours=24)
    assert history.events[0]["event_type"] == "closed"
    assert str(old.id) in history.events[0]["reason"]
    assert events.events[0].conversation_id == conversation.id


async def test_inbound_message_after_max_duration_rotates_with_max_duration_reason():
    session = make_session()
    old = make_conversation(session_id=session.id, started_at=T0, last_inbound_at=T0 + timedelta(days=6, hours=23))
    session.conversation_id = old.id
    tracker, repo, _, _ = _tracker(old)

    conversation = await tracker.record_inbound(session=session, text="otra vez", now=T0 + timedelta(days=7, hours=1))

    assert conversation.id != old.id
    assert repo.conversations[old.id].close_reason == "max_duration"


async def test_inbound_message_on_an_already_closed_conversation_opens_a_new_one_without_reclosing():
    session = make_session()
    old = make_conversation(session_id=session.id, status="closed", close_reason="inactivity", closed_at=T0)
    session.conversation_id = old.id
    tracker, _, _, history = _tracker(old)

    conversation = await tracker.record_inbound(session=session, text="hola", now=T0 + timedelta(hours=1))

    assert conversation.id != old.id
    assert history.events == []


async def test_session_pointing_to_an_unknown_conversation_opens_a_new_one():
    session = make_session()
    session.conversation_id = make_conversation().id
    tracker, repo, _, _ = _tracker()

    conversation = await tracker.record_inbound(session=session, text="hola", now=T0)

    assert session.conversation_id == conversation.id
    assert list(repo.conversations) == [conversation.id]


async def test_outbound_message_is_recorded_as_bot_in_the_current_conversation():
    session = make_session(current_app="langflow")
    current = make_conversation(session_id=session.id)
    session.conversation_id = current.id
    tracker, repo, events, _ = _tracker(current)

    conversation = await tracker.record_outbound(session=session, text="respuesta", now=T0)

    assert conversation.id == current.id
    assert repo.recorded == [{"conversation_id": current.id, "direction": "outbound", "at": T0}]
    [event] = events.events
    assert event.direction == "outbound"
    assert event.sender_type == "bot"
    assert event.app == "langflow"
    assert event.text == "respuesta"


async def test_outbound_message_without_a_conversation_is_not_recorded():
    session = make_session()
    tracker, repo, events, _ = _tracker()

    assert await tracker.record_outbound(session=session, text="respuesta", now=T0) is None
    assert repo.recorded == []
    assert events.events == []


async def test_outbound_message_for_an_unknown_conversation_is_not_recorded():
    session = make_session()
    session.conversation_id = make_conversation().id
    tracker, repo, events, _ = _tracker()

    assert await tracker.record_outbound(session=session, text="respuesta", now=T0) is None
    assert events.events == []
