"""Tests for DemoConversationRecorder: share link chats recorded as "demo"
conversations, not billed, with the agent's reply in the same one."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.services.conversation_tracker import ConversationTracker
from app.application.services.demo_conversations import DEMO_CHANNEL, DemoConversationRecorder
from app.application.use_cases.conversation_contacts import ManageConversationContactsUseCase
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.domain.models.conversation import ConversationLifecyclePolicy
from app.domain.models.message_envelope import MessageEnvelope, MessageMeta
from app.domain.models.project import Project
from api_gateway.tests.support.fakes import (
    FakeContactRepo,
    FakeConversationEventPublisher,
    FakeConversationRepository,
    FakeSessionHistoryRepository,
    FakeSessionRepository,
    FakeWSRegistry,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc)


class FakeProjects:
    def __init__(self, *projects):
        self.projects = {p.id: p for p in projects}

    async def get_by_id(self, project_id):
        return self.projects.get(project_id)


class World:
    def __init__(self, project_exists=True):
        self.tenant_id = uuid4()
        self.project = Project(id=uuid4(), tenant_id=self.tenant_id, name="P", slug="p", created_at=NOW, updated_at=NOW)
        self.share_id, self.agent_id = uuid4(), uuid4()
        self.sessions = FakeSessionRepository()
        self.history = FakeSessionHistoryRepository()
        self.conversations = FakeConversationRepository()
        self.events = FakeConversationEventPublisher()
        self.contacts = FakeContactRepo()
        self.tracker = ConversationTracker(
            conversation_repo=self.conversations,
            event_publisher=self.events,
            session_history_repo=self.history,
            policy=ConversationLifecyclePolicy(inactivity=timedelta(hours=1), max_duration=timedelta(hours=24)),
        )
        self.recorder = DemoConversationRecorder(
            sessions=self.sessions,
            history=self.history,
            tracker=self.tracker,
            projects=FakeProjects(*([self.project] if project_exists else [])),
            session_ttl_seconds=3600,
            contacts=ManageConversationContactsUseCase(contacts=self.contacts),
        )
        self.session_id = f"share:{self.share_id}:visitor-12345678-abcd"

    async def visitor_says(self, text, now=NOW):
        return await self.recorder.record_inbound(
            session_id=self.session_id, share_id=self.share_id, agent_id=self.agent_id,
            project_id=self.project.id, visitor_id="visitor-12345678-abcd", text=text, now=now,
        )


async def test_a_visitor_message_opens_a_demo_conversation_that_is_not_billed():
    world = World()

    await world.visitor_says("Hola, ¿qué planes tenéis?")

    session = world.sessions.sessions[world.session_id]
    assert session.channel_type == DEMO_CHANNEL == "demo"
    assert session.tenant_id == world.tenant_id and session.project_id == world.project.id
    assert session.agent_id == world.agent_id and session.channel_connection_id == world.share_id
    assert session.user_identifier == "Demo · visitante visitor-"
    [conversation] = world.conversations.conversations.values()
    assert conversation.channel_type == "demo" and conversation.tenant_id == world.tenant_id
    [event] = world.events.events
    assert event.direction == "inbound" and event.text == "Hola, ¿qué planes tenéis?"
    assert event.billable is False
    assert [e["event_type"] for e in world.history.events] == ["started"]


async def test_later_messages_stay_in_the_same_conversation():
    world = World()

    first = await world.visitor_says("Hola")
    second = await world.visitor_says("¿Y el precio?", now=NOW + timedelta(minutes=2))

    assert first == second == next(iter(world.conversations.conversations))

    assert len(world.conversations.conversations) == 1
    assert [e.text for e in world.events.events] == ["Hola", "¿Y el precio?"]
    assert [e["event_type"] for e in world.history.events] == ["started"]


async def test_the_agents_reply_is_recorded_in_the_visitors_conversation():
    world = World()
    await world.visitor_says("Hola")
    outbound = HandleOutboundResponseUseCase(
        ws_registry=FakeWSRegistry(connected_conversations=[world.session_id]),
        session_repo=world.sessions,
        session_history_repo=world.history,
        session_ttl_seconds=3600,
        conversation_tracker=world.tracker,
    )
    reply = MessageEnvelope(
        meta=MessageMeta(message_id=str(uuid4()), timestamp=NOW, direction="outbound", conversation_id=world.session_id),
        transport="kafka",
        channel="webchat-share",
        payload={"message": "¡Hola! Tenemos tres planes."},
    )

    await outbound.deliver(reply)

    assert [(e.direction, e.text) for e in world.events.events] == [
        ("inbound", "Hola"),
        ("outbound", "¡Hola! Tenemos tres planes."),
    ]
    assert len({e.conversation_id for e in world.events.events}) == 1


async def test_the_visitor_gets_a_generic_card_completed_with_what_they_write():
    world = World()
    await world.visitor_says("Hola")
    world.sessions.sessions[world.session_id].record_message(
        direction="outbound", text="¿Me dejas tu email?", app="langflow", timestamp=NOW
    )

    await world.visitor_says("claro: ana@example.com", now=NOW + timedelta(minutes=1))

    [card] = world.contacts.contacts.values()
    assert card.channel_type == "demo" and card.identifier == "Demo · visitante visitor-"
    assert (card.name, card.email) == ("client:demo-visitor1", "ana@example.com")


async def test_console_test_replies_are_not_recorded():
    world = World()
    outbound = HandleOutboundResponseUseCase(
        ws_registry=FakeWSRegistry(connected_conversations=["test:a:v"]),
        session_repo=world.sessions,
        session_history_repo=world.history,
        session_ttl_seconds=3600,
        conversation_tracker=world.tracker,
    )
    reply = MessageEnvelope(
        meta=MessageMeta(message_id=str(uuid4()), timestamp=NOW, direction="outbound", conversation_id="test:a:v"),
        transport="kafka",
        channel="webchat-test",
        payload={"message": "Hola"},
    )

    await outbound.deliver(reply)

    assert world.events.events == []


async def test_a_project_that_no_longer_exists_records_nothing():
    world = World(project_exists=False)

    await world.visitor_says("Hola")

    assert world.sessions.sessions == {} and world.events.events == []


async def test_a_recording_failure_never_breaks_the_chat():
    world = World()
    world.events.fail = True

    assert await world.visitor_says("Hola") is None  # and it must not raise
