"""Tests for CloseExpiredConversationsUseCase (the periodic sweep)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.use_cases.close_expired_conversations import CloseExpiredConversationsUseCase
from app.domain.models.conversation import ConversationLifecyclePolicy
from api_gateway.tests.support.fakes import (
    FakeConversationRepository,
    FakeSessionHistoryRepository,
    make_conversation,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
POLICY = ConversationLifecyclePolicy(inactivity=timedelta(hours=24), max_duration=timedelta(days=7))


def _closed(**overrides):
    return make_conversation(status="closed", close_reason="inactivity", closed_at=NOW, **overrides)


async def test_passes_the_policy_limits_to_the_repository_and_logs_a_closed_event_per_conversation():
    repo = FakeConversationRepository()
    history = FakeSessionHistoryRepository()
    closed = [_closed(), _closed()]
    repo.expired_batches = [closed]
    use_case = CloseExpiredConversationsUseCase(
        conversation_repo=repo, session_history_repo=history, policy=POLICY, batch_size=10
    )

    count = await use_case.execute(NOW)

    assert count == 2
    assert repo.close_expired_calls == [
        {"now": NOW, "inactivity": timedelta(hours=24), "max_duration": timedelta(days=7), "limit": 10}
    ]
    assert [event["session_id"] for event in history.events] == [c.session_id for c in closed]
    assert all(event["event_type"] == "closed" for event in history.events)
    assert "inactivity" in history.events[0]["reason"]


async def test_keeps_sweeping_while_batches_come_back_full():
    repo = FakeConversationRepository()
    repo.expired_batches = [[_closed(), _closed()], [_closed(), _closed()], [_closed()]]
    use_case = CloseExpiredConversationsUseCase(
        conversation_repo=repo, session_history_repo=FakeSessionHistoryRepository(), policy=POLICY, batch_size=2
    )

    assert await use_case.execute(NOW) == 5
    assert len(repo.close_expired_calls) == 3


async def test_nothing_to_close():
    repo = FakeConversationRepository()
    history = FakeSessionHistoryRepository()
    use_case = CloseExpiredConversationsUseCase(conversation_repo=repo, session_history_repo=history, policy=POLICY)

    assert await use_case.execute(NOW) == 0
    assert history.events == []
