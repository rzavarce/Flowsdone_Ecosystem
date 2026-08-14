"""Tests for RouteChannelMessageUseCase and build_conversation_id."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api_gateway.app.application.use_cases.ingest_message import IngestMessageUseCase
from api_gateway.app.application.use_cases.route_channel_message import (
    ChannelMessageNotRoutable,
    RouteChannelMessageUseCase,
    build_conversation_id,
)
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakePublisherFactory,
    make_channel_resolution,
)

pytestmark = pytest.mark.anyio


def test_build_conversation_id_is_deterministic_and_namespaced():
    project_id = uuid4()

    conversation_id = build_conversation_id(project_id, "telegram", "chat-42")

    assert conversation_id == f"{project_id}:telegram:chat-42"


async def test_unresolved_channel_raises_not_routable():
    repo = FakeChannelConnectionRepo(resolution=None)
    ingest = IngestMessageUseCase(publisher_factory=FakePublisherFactory())
    use_case = RouteChannelMessageUseCase(repo, ingest)

    with pytest.raises(ChannelMessageNotRoutable):
        await use_case.execute(
            channel_type="telegram",
            external_id="unknown-bot",
            external_conversation_key="chat-1",
            sender_id="chat-1",
            payload={"message": "hola"},
        )


async def test_resolved_channel_ingests_with_namespaced_conversation_id():
    resolution = make_channel_resolution(channel_type="telegram", langflow_flow_id="flow-9")
    repo = FakeChannelConnectionRepo(resolution=resolution)
    publisher_factory = FakePublisherFactory()
    ingest = IngestMessageUseCase(publisher_factory=publisher_factory)
    use_case = RouteChannelMessageUseCase(repo, ingest)

    await use_case.execute(
        channel_type="telegram",
        external_id="123:ABC",
        external_conversation_key="chat-1",
        sender_id="chat-1",
        payload={"message": "hola"},
    )

    envelope = publisher_factory.publisher.published[0]["message"]
    assert envelope["meta"]["workflow_id"] == "flow-9"
    assert envelope["meta"]["conversation_id"] == f"{resolution.project_id}:telegram:chat-1"
    assert envelope["meta"]["channel_connection_id"] == str(resolution.channel_connection_id)
    assert envelope["meta"]["external_conversation_key"] == "chat-1"
    assert envelope["channel"] == "telegram"
    # RouteChannelMessageUseCase defaults to transport="kafka" for chat channels.
    assert publisher_factory.requested_transports == ["kafka"]


async def test_transport_can_be_overridden_for_the_voice_channel():
    resolution = make_channel_resolution(channel_type="voice", langflow_flow_id="flow-9")
    repo = FakeChannelConnectionRepo(resolution=resolution)
    publisher_factory = FakePublisherFactory()
    ingest = IngestMessageUseCase(publisher_factory=publisher_factory)
    use_case = RouteChannelMessageUseCase(repo, ingest)

    await use_case.execute(
        channel_type="voice",
        external_id="+15559998888",
        external_conversation_key="CA123",
        sender_id="+15550001111",
        payload={"message": "hola"},
        transport="kafka_voice",
    )

    # The voice channel routes to its own dedicated topic instead of
    # the default "kafka" transport, keeping it isolated from text
    # channels without RouteChannelMessageUseCase knowing about Kafka
    # topics itself.
    assert publisher_factory.requested_transports == ["kafka_voice"]
