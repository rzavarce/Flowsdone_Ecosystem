"""Tests for IngestMessageUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.ingest_message import IngestMessageUseCase
from api_gateway.tests.support.fakes import FakePublisherFactory

pytestmark = pytest.mark.anyio


async def test_builds_and_publishes_inbound_envelope_keyed_by_channel():
    factory = FakePublisherFactory()
    use_case = IngestMessageUseCase(publisher_factory=factory)

    await use_case.execute(
        workflow_id="flow-1",
        conversation_id="conv-1",
        sender_id="user-1",
        transport="kafka",
        payload={"message": "hola"},
        channel="telegram",
        channel_connection_id="cc-1",
        external_conversation_key="chat-1",
    )

    assert factory.requested_transports == ["kafka"]
    published = factory.publisher.published
    assert len(published) == 1

    call = published[0]
    assert call["key"] == "telegram"

    envelope = call["message"]
    assert envelope["meta"]["direction"] == "inbound"
    assert envelope["meta"]["workflow_id"] == "flow-1"
    assert envelope["meta"]["conversation_id"] == "conv-1"
    assert envelope["meta"]["channel_connection_id"] == "cc-1"
    assert envelope["meta"]["external_conversation_key"] == "chat-1"
    assert envelope["transport"] == "kafka"
    assert envelope["channel"] == "telegram"
    assert envelope["payload"] == {"message": "hola"}
    assert envelope["response_to"] is None


async def test_channel_defaults_to_sender_id_when_not_given():
    factory = FakePublisherFactory()
    use_case = IngestMessageUseCase(publisher_factory=factory)

    await use_case.execute(
        workflow_id="flow-1",
        conversation_id="conv-1",
        sender_id="webchat",
        transport="kafka",
        payload={"message": "hola"},
    )

    envelope = factory.publisher.published[0]["message"]
    assert envelope["channel"] == "webchat"
    assert factory.publisher.published[0]["key"] == "webchat"
