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


# --- notify_failure() ----------------------------------------------------


async def test_notify_failure_answers_the_customer_with_the_failure_message():
    publisher = FakePublisher()
    use_case = HandleOutboundResponseUseCase(publisher=publisher, failure_message="Ahora no puedo, perdona.")
    envelope = _envelope()

    await use_case.notify_failure(envelope, RuntimeError("FLOWSDONE_OPENAI_KEY variable not found"))

    published_envelope = publisher.published[0]["message"]
    assert published_envelope["payload"]["message"] == "Ahora no puedo, perdona."
    assert published_envelope["meta"]["direction"] == "outbound"
    assert published_envelope["response_to"] == envelope.meta.message_id


async def test_notify_failure_hides_the_error_from_real_customers():
    publisher = FakePublisher()
    use_case = HandleOutboundResponseUseCase(publisher=publisher)

    await use_case.notify_failure(_envelope(), RuntimeError("secret internal detail"))

    message = publisher.published[0]["message"]["payload"]["message"]
    assert "secret internal detail" not in message
    assert message == hor_module.DEFAULT_FAILURE_MESSAGE


async def test_notify_failure_shows_the_error_on_the_console_test_channel():
    publisher = FakePublisher()
    use_case = HandleOutboundResponseUseCase(publisher=publisher)
    envelope = _envelope().model_copy(update={"channel": "webchat-test"})

    await use_case.notify_failure(envelope, RuntimeError("variable not found " + "x" * 1000))

    message = publisher.published[0]["message"]["payload"]["message"]
    assert message.startswith(hor_module.DEFAULT_FAILURE_MESSAGE)
    assert "[Detalle para pruebas] variable not found" in message
    assert len(message) < len(hor_module.DEFAULT_FAILURE_MESSAGE) + 550  # detail is truncated


async def test_notify_failure_reaches_a_live_websocket():
    ws_registry = FakeWSRegistry(connected_conversations=["conv-1"])
    use_case = HandleOutboundResponseUseCase(ws_registry=ws_registry)

    await use_case.notify_failure(_envelope(), RuntimeError("boom"))

    assert ws_registry.sent[0]["message"]["message"] == hor_module.DEFAULT_FAILURE_MESSAGE


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


class FakeCallbackSender:
    """Records callbacks; can pretend to fail."""

    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    async def send(self, url, body):
        self.calls.append((url, body))
        return self.ok


async def test_execute_sends_the_callback_through_the_port():
    sender = FakeCallbackSender()
    use_case = HandleOutboundResponseUseCase(callback_sender=sender)
    envelope = _envelope()
    envelope.payload["callback_url"] = "https://example.com/callback"

    await use_case.execute(envelope, {"message": "hola"})

    [(url, body)] = sender.calls
    assert url == "https://example.com/callback"
    assert body == {"conversation_id": "conv-1", "message": "hola"}


async def test_without_a_callback_sender_no_callback_is_made():
    use_case = HandleOutboundResponseUseCase()
    envelope = _envelope()
    envelope.payload["callback_url"] = "http://api:8000/internal/admin/tenants"

    # Skipped (and logged), never raised.
    await use_case.execute(envelope, {"message": "hola"})


async def test_execute_never_raises_even_if_callback_fails():
    use_case = HandleOutboundResponseUseCase(callback_sender=FakeCallbackSender(ok=False))
    envelope = _envelope()
    envelope.payload["callback_url"] = "https://example.com/callback"

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
            "config": connection.config,
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


# --- conversation tracking on delivery ----------------------------------


def _tracked_outbound_use_case(session, *, publisher_fails: bool = False):
    from datetime import timedelta

    from app.application.services.conversation_tracker import ConversationTracker
    from app.domain.models.conversation import ConversationLifecyclePolicy
    from api_gateway.tests.support.fakes import (
        FakeConversationEventPublisher,
        FakeConversationRepository,
        make_conversation,
    )

    connection = make_channel_connection(channel_type="telegram")
    conversation = make_conversation(session_id=session.id)
    session.conversation_id = conversation.id
    events = FakeConversationEventPublisher(fail=publisher_fails)
    tracker = ConversationTracker(
        conversation_repo=FakeConversationRepository(conversation),
        event_publisher=events,
        session_history_repo=FakeSessionHistoryRepository(),
        policy=ConversationLifecyclePolicy(inactivity=timedelta(hours=24), max_duration=timedelta(days=7)),
    )
    sender = FakeChannelSender()
    use_case = HandleOutboundResponseUseCase(
        channel_connection_repo=FakeChannelConnectionRepo(connection=connection),
        channel_senders={"telegram": sender},
        session_repo=FakeSessionRepository(session=session),
        session_history_repo=FakeSessionHistoryRepository(),
        conversation_tracker=tracker,
    )
    envelope = _envelope(channel_connection_id=str(connection.id))
    envelope.channel = "telegram"
    envelope.payload["message"] = "respuesta"
    return use_case, envelope, events, conversation, sender


async def test_deliver_records_the_outbound_message_in_the_current_conversation():
    session = make_session(id="conv-1", current_app="langflow")
    use_case, envelope, events, conversation, _ = _tracked_outbound_use_case(session)

    await use_case.deliver(envelope)

    [event] = events.events
    assert event.conversation_id == conversation.id
    assert event.direction == "outbound"
    assert event.text == "respuesta"


async def test_deliver_never_raises_when_conversation_recording_fails():
    session = make_session(id="conv-1")
    use_case, envelope, _, _, sender = _tracked_outbound_use_case(session, publisher_fails=True)

    await use_case.deliver(envelope)

    assert len(sender.sent) == 1
