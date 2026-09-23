"""Integration test for ClickHouseUsageStore against a real ClickHouse
(TEST_CLICKHOUSE_* - a throwaway database created with
scripts/clickhouse/init-clickhouse.sh)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.adapters.outbound.clickhouse.usage_store import ClickHouseUsageStore
from app.domain.models.usage import UsageEvent

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_CLICKHOUSE_URL"), reason="TEST_CLICKHOUSE_URL not set"),
]


async def test_usage_is_deduplicated_and_aggregated_per_day_and_meter():
    client = ClickHouseHttpClient(
        base_url=os.environ["TEST_CLICKHOUSE_URL"],
        database=os.environ["TEST_CLICKHOUSE_DATABASE"],
        user=os.environ["TEST_CLICKHOUSE_USER"],
        password=os.environ["TEST_CLICKHOUSE_PASSWORD"],
    )
    store = ClickHouseUsageStore(client)
    tenant, conversation = uuid4(), uuid4()

    def event(quantity, day, unit="input_token"):
        return UsageEvent(
            event_id=uuid4(), timestamp=datetime(2026, 9, day, 10, tzinfo=timezone.utc), tenant_id=tenant,
            project_id=uuid4(), conversation_id=conversation, channel_type="telegram", kind="llm",
            provider="openai", sku="gpt-4.1-mini", quantity=Decimal(quantity), unit=unit,
        )

    first = event(100, 1)
    try:
        await store.insert_usage([first, event(50, 1), event(7, 2), event(3, 1, unit="output_token")])
        await store.insert_usage([first])  # redelivered
        daily = await store.aggregate_daily(
            start=datetime(2026, 9, 1, tzinfo=timezone.utc), end=datetime(2026, 10, 1, tzinfo=timezone.utc),
            tenant_id=tenant,
        )
        by_conversation = await store.aggregate_conversation(tenant_id=tenant, conversation_id=conversation)
    finally:
        await client.aclose()

    summary = {(str(a.day), a.unit): a.quantity for a in daily}
    assert summary == {
        ("2026-09-01", "input_token"): Decimal(150),
        ("2026-09-01", "output_token"): Decimal(3),
        ("2026-09-02", "input_token"): Decimal(7),
    }
    assert {(str(a.day), a.unit): a.quantity for a in by_conversation} == summary
