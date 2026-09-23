"""Tests for the ConversationEventPublisherPort implementations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.adapters.outbound.conversations.event_publishers import (
    BrokerConversationEventPublisher,
    NullConversationEventPublisher,
)
from app.domain.models.conversation_message import MESSAGE_RECORDED_EVENT, ConversationMessageRecorded
from api_gateway.tests.support.fakes import FakePublisher

pytestmark = pytest.mark.anyio


def _event() -> ConversationMessageRecorded:
    return ConversationMessageRecorded(
        message_id=uuid4(),
        timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        tenant_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        conversation_id=uuid4(),
        session_id="p:telegram:chat-1",
        channel_type="telegram",
        channel_connection_id=uuid4(),
        direction="inbound",
        sender_type="contact",
        app="langflow",
        contact="user-1",
        text="hola",
    )


async def test_publishes_json_keyed_by_conversation_id():
    broker = FakePublisher()
    event = _event()

    await BrokerConversationEventPublisher(broker).publish_message_recorded(event)

    [published] = broker.published
    assert published["key"] == str(event.conversation_id)
    assert published["message"]["event_type"] == MESSAGE_RECORDED_EVENT
    assert published["message"]["message_id"] == str(event.message_id)
    assert published["message"]["timestamp"].startswith("2026-09-01T12:00:00")


async def test_null_publisher_drops_events():
    await NullConversationEventPublisher().publish_message_recorded(_event())
