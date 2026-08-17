"""Tests for LangflowAppConnector."""

from __future__ import annotations

import pytest

from api_gateway.app.adapters.outbound.apps.langflow_app_connector import LangflowAppConnector
from api_gateway.app.application.use_cases.ingest_message import IngestMessageUseCase
from api_gateway.tests.support.fakes import FakePublisherFactory, make_session

pytestmark = pytest.mark.anyio


async def test_handle_turn_publishes_to_kafka_and_returns_none():
    publisher_factory = FakePublisherFactory()
    ingest = IngestMessageUseCase(publisher_factory=publisher_factory)
    connector = LangflowAppConnector(ingest)
    session = make_session(
        id="proj:telegram:chat-1",
        channel_type="telegram",
        external_conversation_key="chat-1",
        user_identifier="user-42",
        variables={"langflow_flow_id": "flow-123"},
    )

    result = await connector.handle_turn(
        session=session, message_text="hola", raw_payload={"raw": True}
    )

    assert result is None
    assert publisher_factory.requested_transports == ["kafka"]
    envelope = publisher_factory.publisher.published[0]["message"]
    assert envelope["meta"]["workflow_id"] == "flow-123"
    assert envelope["meta"]["conversation_id"] == "proj:telegram:chat-1"
    assert envelope["meta"]["external_conversation_key"] == "chat-1"
    assert envelope["channel"] == "telegram"
    assert envelope["payload"]["message"] == "hola"


async def test_handle_turn_uses_the_voice_transport_for_the_voice_channel():
    publisher_factory = FakePublisherFactory()
    ingest = IngestMessageUseCase(publisher_factory=publisher_factory)
    connector = LangflowAppConnector(ingest)
    session = make_session(
        id="proj:voice:CA123",
        channel_type="voice",
        external_conversation_key="CA123",
        variables={"langflow_flow_id": "flow-123"},
    )

    await connector.handle_turn(session=session, message_text="hola", raw_payload={})

    assert publisher_factory.requested_transports == ["kafka_voice"]
