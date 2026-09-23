"""Tests for ArchiveConversationMessagesUseCase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.use_cases.archive_conversation_messages import ArchiveConversationMessagesUseCase
from app.domain.models.conversation_message import ConversationMessageRecorded
from api_gateway.tests.support.fakes import FakeMessageArchive

pytestmark = pytest.mark.anyio

RETENTION = timedelta(days=183)


def _event(**overrides) -> dict:
    event = ConversationMessageRecorded(
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
    ).model_dump(mode="json")
    event.update(overrides)
    return event


async def test_archives_message_events_with_the_configured_retention():
    archive = FakeMessageArchive()
    use_case = ArchiveConversationMessagesUseCase(archive=archive, retention=RETENTION)
    raw = [_event(text="uno"), _event(text="dos")]

    assert await use_case.execute(raw) == 2

    [batch] = archive.batches
    assert batch["retention"] == RETENTION
    assert [e.text for e in batch["events"]] == ["uno", "dos"]


async def test_skips_other_event_types_undecodable_and_malformed_events():
    archive = FakeMessageArchive()
    use_case = ArchiveConversationMessagesUseCase(archive=archive, retention=RETENTION)
    raw = [_event(), {"event_type": "conversation.other"}, None, _event(conversation_id="not-a-uuid")]

    assert await use_case.execute(raw) == 1
    assert len(archive.batches[0]["events"]) == 1


async def test_does_not_call_the_archive_for_an_empty_batch():
    archive = FakeMessageArchive()
    use_case = ArchiveConversationMessagesUseCase(archive=archive, retention=RETENTION)

    assert await use_case.execute([None]) == 0
    assert archive.batches == []


async def test_propagates_archive_failures_so_the_batch_is_retried():
    use_case = ArchiveConversationMessagesUseCase(archive=FakeMessageArchive(fail=True), retention=RETENTION)

    with pytest.raises(RuntimeError):
        await use_case.execute([_event()])


async def test_meters_the_usage_of_the_archived_messages():
    from api_gateway.tests.support.fakes import FakeUsageStore

    store = FakeUsageStore()
    use_case = ArchiveConversationMessagesUseCase(archive=FakeMessageArchive(), retention=RETENTION, usage_store=store)

    await use_case.execute([_event(), _event(direction="outbound", sender_type="bot")])

    assert sorted((e.kind, e.sku) for e in store.events.values()) == [
        ("channel", "message.inbound"),
        ("channel", "message.outbound"),
        ("platform", "ai_message"),
    ]


async def test_usage_failure_fails_the_batch_so_it_is_retried():
    from api_gateway.tests.support.fakes import FakeUsageStore

    use_case = ArchiveConversationMessagesUseCase(
        archive=FakeMessageArchive(), retention=RETENTION, usage_store=FakeUsageStore(fail=True)
    )

    with pytest.raises(RuntimeError):
        await use_case.execute([_event()])
