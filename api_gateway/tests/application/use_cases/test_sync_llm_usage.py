"""Tests for SyncLlmUsageUseCase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.application.use_cases.sync_llm_usage import CURSOR_NAME, SyncLlmUsageUseCase
from app.domain.ports.outbound import LlmGeneration
from api_gateway.tests.support.fakes import (
    FakeConversationRepository,
    FakeLlmUsageSource,
    FakeSyncCursors,
    FakeUsageStore,
    make_conversation,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _generation(id, session_id, start_time, **tokens):
    return LlmGeneration(
        id=id, trace_id=f"t-{id}", session_id=session_id, model="gpt-4.1-mini", start_time=start_time,
        input_tokens=tokens.get("input", 100), output_tokens=tokens.get("output", 10),
        cached_input_tokens=tokens.get("cached", 0),
    )


def _use_case(generations, *conversations, cursor=None):
    source = FakeLlmUsageSource(generations)
    store = FakeUsageStore()
    cursors = FakeSyncCursors(**({CURSOR_NAME: cursor} if cursor else {}))
    use_case = SyncLlmUsageUseCase(
        source=source, conversation_repo=FakeConversationRepository(*conversations),
        usage_store=store, cursors=cursors,
    )
    return use_case, source, store, cursors


async def test_first_run_reads_the_initial_lookback_and_stops_lag_before_now():
    use_case, source, _, cursors = _use_case([])

    await use_case.execute(NOW)

    assert source.windows == [(NOW - timedelta(days=1), NOW - timedelta(minutes=2))]
    assert cursors.positions[CURSOR_NAME] == NOW - timedelta(minutes=2)


async def test_next_runs_reread_an_overlap_before_the_cursor():
    cursor = NOW - timedelta(minutes=7)
    use_case, source, _, _ = _use_case([], cursor=cursor)

    await use_case.execute(NOW)

    assert source.windows[0][0] == cursor - timedelta(hours=1)


async def test_a_long_outage_is_caught_up_in_bounded_windows():
    cursor = NOW - timedelta(days=5)
    use_case, source, _, cursors = _use_case([], cursor=cursor)

    await use_case.execute(NOW)

    start, end = source.windows[0]
    assert end - start == timedelta(days=1)
    assert cursors.positions[CURSOR_NAME] == end


async def test_generations_are_attributed_to_their_conversation_and_unknown_sessions_skipped():
    conversation = make_conversation()
    at = NOW - timedelta(hours=2)
    generations = [
        _generation("g1", str(conversation.id), at, input=500, output=40, cached=100),
        _generation("g2", "proj:webchat:abc", at),  # not a conversation id
        _generation("g3", "8b9cad0e-0000-4000-8000-000000000000", at),  # unknown conversation
        _generation("g4", None, at),
    ]
    use_case, _, store, _ = _use_case(generations, conversation)

    result = await use_case.execute(NOW)

    assert (result.generations, result.attributed, result.unattributed, result.events) == (4, 1, 3, 3)
    assert {e.unit for e in store.events.values()} == {"input_token", "output_token", "cached_input_token"}
    assert all(e.tenant_id == conversation.tenant_id for e in store.events.values())


async def test_rereading_the_same_generations_does_not_duplicate_usage():
    conversation = make_conversation()
    generations = [_generation("g1", str(conversation.id), NOW - timedelta(minutes=30))]
    use_case, _, store, _ = _use_case(generations, conversation)

    await use_case.execute(NOW)
    await use_case.execute(NOW + timedelta(minutes=5))  # overlap re-reads g1

    assert len(store.events) == 2
