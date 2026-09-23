"""Tests for GetConversationDetailUseCase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.use_cases.conversation_queries import GetConversationDetailUseCase
from app.domain.models.usage import UsageEvent
from api_gateway.tests.support.fakes import (
    FakeConversationRepository,
    FakeCostRateRepo,
    FakeUsageStore,
    make_conversation,
    make_cost_rate,
)

pytestmark = pytest.mark.anyio


class _Archive:
    def __init__(self, messages):
        self.messages = messages
        self.calls = []

    async def list_messages(self, *, tenant_id, conversation_id, limit=500):
        self.calls.append((tenant_id, conversation_id, limit))
        return self.messages


async def test_detail_has_transcript_rated_usage_and_tokens():
    conversation = make_conversation()
    usage = FakeUsageStore()
    when = datetime(2026, 9, 1, tzinfo=timezone.utc)
    for unit, qty in (("input_token", 2_000_000), ("output_token", 100), ("cached_input_token", 5)):
        await usage.insert_usage([UsageEvent(
            event_id=uuid4(), timestamp=when, tenant_id=conversation.tenant_id, project_id=conversation.project_id,
            conversation_id=conversation.id, kind="llm", provider="openai", sku="gpt-4.1-mini", quantity=Decimal(qty), unit=unit,
        )])
    archive = _Archive(["m1", "m2"])
    use_case = GetConversationDetailUseCase(
        conversations=FakeConversationRepository(conversation), archive=archive, usage_store=usage,
        cost_rates=FakeCostRateRepo(make_cost_rate(price_micros=400_000)),
    )

    detail = await use_case.execute(conversation.id, message_limit=10)

    assert detail.messages == ["m1", "m2"]
    assert archive.calls == [(conversation.tenant_id, conversation.id, 10)]
    assert detail.cost_micros == 800_000
    assert (detail.llm_input_tokens, detail.llm_output_tokens, detail.llm_cached_input_tokens) == (2_000_000, 100, 5)


async def test_unknown_conversation_is_none():
    use_case = GetConversationDetailUseCase(
        conversations=FakeConversationRepository(), archive=_Archive([]), usage_store=FakeUsageStore(),
        cost_rates=FakeCostRateRepo(),
    )

    assert await use_case.execute(uuid4()) is None
