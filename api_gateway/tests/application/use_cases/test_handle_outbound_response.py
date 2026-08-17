"""Tests for HandleOutboundResponseUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.application.use_cases import handle_outbound_response as hor_module
from app.application.use_cases.handle_outbound_response import (
    HandleOutboundResponseUseCase,
)
from app.domain.models.message_envelope import MessageEnvelope, MessageMeta
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeChannelSender,
    FakePublisher,
    FakeSessionHistoryRepository,
    FakeSessionRepository,
    FakeWSRegistry,
    make_channel_connection,
    make_session,
)

pytestmark = pytest.mark.anyio


def _envelope(**meta_overrides) -> MessageEnvelope:
    meta = MessageMeta(
        message_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        direction="inbound",
        conversation_id="conv-1",
        **meta_overrides,
    )
    return MessageEnvelope(meta=meta, transport="kafka", channel="telegram", payload={})


# --- _extract_text -----------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("plain string", "plain string"),
        ("   ", None),
        (None, None),
        ({"message": "hi"}, "hi"),
        ({"response": "hi"}, "hi"),
        ({"output": {"message": "nested"}}, "nested"),
        ({"outputs": [{"content": "deep"}]}, "deep"),
        ({"data": {"results": [{"text": "very deep"}]}}, "very deep"),
        ({"detail": "an error"}, "an error"),
        ([{"message": ""}, {"message": "second wins"}], "second wins"),
        ({"unrelated": "nope"}, None),
        ([], None),
    ],
)
def test_extract_text_handles_common_langflow_shapes(value, expected):
    use_case = HandleOutboundResponseUseCase()

    assert use_case._extract_text(value) == expected


# --- execute() -----------------------------------------------------------


async def test_execute_publishes_outbound_envelope_with_extracted_text():
    publisher = FakePublisher()
    use_case = HandleOutboundResponseUseCase(publisher=publisher)
    envelope = _envelope()

    await use_case.execute(envelope, {"message": "hola desde langflow"})

    assert len(publisher.published) == 1
    published_envelope = publisher.published[0]["message"]
    assert published_envelope["payload"]["response"] == "hola desde langflow"
    assert published_envelope["meta"]["direction"] == "outbound"
    assert published_envelope["response_to"] == envelope.meta.message_id


async def test_execute_falls_back_to_default_message_when_unparseable():
    publisher = FakePublisher()
    use_case = HandleOutboundResponseUseCase(publisher=publisher)
    envelope = _envelope()

    await use_case.execute(envelope, {"unrelated": "nope"})

    published_envelope = publisher.published[0]["message"]
    assert published_envelope["payload"]["response"] == (
        "The workflow did not return a valid response."
    )


async def test_execute_pushes_to_websocket_when_conversation_has_live_connection():
    ws_registry = FakeWSRegistry(connected_conversations=["conv-1"])
    use_case = HandleOutboundResponseUseCase(ws_registry=ws_registry)
    envelope = _envelope()

    await use_case.execute(envelope, {"message": "hola"})

    assert ws_registry.sent[0]["conversation_id"] == "conv-1"
    assert ws_registry.sent[0]["message"]["response"] == "hola"


async def test_execute_never_raises_even_if_websocket_send_fails():
    ws_registry = FakeWSRegistry(fail=True)
    use_case = HandleOutboundResponseUseCase(ws_registry=ws_registry)
    envelope = _envelope()

    # Should not raise, even though ws_registry.send() always fails.
    await use_case.execute(envelope, {"message": "hola"})


async def test_execute_posts_to_callback_url_when_present(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(hor_module.httpx, "AsyncClient", fake_client.as_constructor())

    use_case = HandleOutboundResponseUseCase()
    envelope = _envelope()
    envelope.payload["callback_url"] = "https://example.com/callback"

    await use_case.execute(envelope, {"message": "hola"})

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0].url == "https://example.com/callback"
    assert fake_client.calls[0].kwargs["json"]["message"] == "hola"


async def test_execute_never_raises_even_if_callback_fails(monkeypatch):
    def _raise(_call):
        raise ConnectionError("network down")

    fake_client = FakeAsyncClient(_raise)
    monkeypatch.setattr(hor_module.httpx, "AsyncClient", fake_client.as_constructor())

    use_case = HandleOutboundResponseUseCase()
    envelope = _envelope()
    envelope.payload["callback_url"] = "https://example.com/callback"

    # Should not raise, even though the callback POST always fails.
    await use_case.execute(envelope, {"message": "hola"})


# --- deliver() -------------------------------------------------------------


async def test_deliver_pushes_to_websocket_for_webchat():
    ws_registry = FakeWSRegistry(connected_conversations=["conv-1"])
    use_case = HandleOutboundResponseUseCase(ws_registry=ws_registry)
    envelope = _envelope()
    envelope.payload["message"] = "respuesta"

    await use_case.deliver(envelope)

    assert ws_registry.sent[0]["message"]["message"] == "respuesta"


async def test_deliver_sends_to_native_channel_sender_when_connection_id_present():
    connection = make_channel_connection(
        channel_type="telegram", external_id="123:ABC", credentials={"telegram_webhook_secret": "s"}
    )
    repo = FakeChannelConnectionRepo(connection=connection)
    sender = FakeChannelSender()

    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=repo, channel_senders={"telegram": sender}
    )
    envelope = _envelope(
        channel_connection_id=str(connection.id), external_conversation_key="chat-99"
    )
    envelope.channel = "telegram"
    envelope.payload["message"] = "respuesta"

    await use_case.deliver(envelope)

    assert sender.sent == [
        {
            "external_id": "123:ABC",
            "recipient_id": "chat-99",
            "text": "respuesta",
            "credentials": {"telegram_webhook_secret": "s"},
        }
    ]


async def test_deliver_is_a_noop_for_webchat_without_channel_connection_id():
    sender = FakeChannelSender()
    use_case = HandleOutboundResponseUseCase(channel_senders={"telegram": sender})
    envelope = _envelope()  # no channel_connection_id -> webchat

    await use_case.deliver(envelope)

    assert sender.sent == []


async def test_deliver_never_raises_when_sender_fails():
    connection = make_channel_connection(channel_type="telegram")
    repo = FakeChannelConnectionRepo(connection=connection)
    sender = FakeChannelSender(fail=True)

    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=repo, channel_senders={"telegram": sender}
    )
    envelope = _envelope(channel_connection_id=str(connection.id))
    envelope.channel = "telegram"

    # Should not raise, even though the sender always fails.
    await use_case.deliver(envelope)


async def test_deliver_records_the_outbound_turn_in_session_history_and_state():
    connection = make_channel_connection(channel_type="telegram", external_id="123:ABC")
    channel_repo = FakeChannelConnectionRepo(connection=connection)
    sender = FakeChannelSender()
    session = make_session(id="conv-1", current_app="langflow")
    session_repo = FakeSessionRepository(session=session)
    session_history_repo = FakeSessionHistoryRepository()

    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=channel_repo,
        channel_senders={"telegram": sender},
        session_repo=session_repo,
        session_history_repo=session_history_repo,
    )
    envelope = _envelope(channel_connection_id=str(connection.id), external_conversation_key="chat-99")
    envelope.channel = "telegram"
    envelope.payload["message"] = "respuesta"

    await use_case.deliver(envelope)

    assert session_history_repo.messages == [
        {
            "session_id": "conv-1",
            "project_id": session.project_id,
            "direction": "outbound",
            "text": "respuesta",
            "app": "langflow",
        }
    ]
    saved_session = session_repo.sessions["conv-1"]
    assert saved_session.last_messages[-1].text == "respuesta"
    assert saved_session.last_messages[-1].direction == "outbound"


async def test_deliver_skips_session_recording_when_ports_not_wired():
    connection = make_channel_connection(channel_type="telegram")
    channel_repo = FakeChannelConnectionRepo(connection=connection)
    sender = FakeChannelSender()

    # No session_repo/session_history_repo given - e.g. webchat delivery.
    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=channel_repo, channel_senders={"telegram": sender}
    )
    envelope = _envelope(channel_connection_id=str(connection.id))
    envelope.channel = "telegram"

    # Should not raise even without session ports wired.
    await use_case.deliver(envelope)


async def test_deliver_skips_session_recording_when_no_session_exists():
    connection = make_channel_connection(channel_type="telegram")
    channel_repo = FakeChannelConnectionRepo(connection=connection)
    sender = FakeChannelSender()
    session_repo = FakeSessionRepository()  # empty - no session for "conv-1"
    session_history_repo = FakeSessionHistoryRepository()

    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=channel_repo,
        channel_senders={"telegram": sender},
        session_repo=session_repo,
        session_history_repo=session_history_repo,
    )
    envelope = _envelope(channel_connection_id=str(connection.id))
    envelope.channel = "telegram"

    await use_case.deliver(envelope)

    assert session_history_repo.messages == []


async def test_deliver_noop_when_connection_not_found():
    repo = FakeChannelConnectionRepo(connection=None)
    sender = FakeChannelSender()
    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=repo, channel_senders={"telegram": sender}
    )
    envelope = _envelope(channel_connection_id=str(uuid4()))
    envelope.channel = "telegram"

    await use_case.deliver(envelope)

    assert sender.sent == []
