"""Tests for QuotaGate."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.quota_gate import QuotaGate
from app.domain.models.usage import UsageEvent
from api_gateway.tests.support.fakes import (
    FakePlanRepo,
    FakeQuotaCounter,
    FakeQuotaNotifier,
    FakeSubscriptionRepo,
    FakeUsageStore,
    make_plan,
    make_subscription,
)

pytestmark = pytest.mark.anyio

WA = "whatsapp_evolution"
NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def _gate(*, included=5, mode="hard_stop", subscribed=True, usage=None, notifier=None):
    plan = make_plan(included_messages={WA: included}, default_overage_mode=mode)
    tenant = uuid4()
    subscriptions = FakeSubscriptionRepo(*([make_subscription(tenant_id=tenant, plan_id=plan.id)] if subscribed else []))
    plans = FakePlanRepo(plan)
    counters = FakeQuotaCounter()
    gate = QuotaGate(
        subscriptions=subscriptions, plans=plans, counters=counters,
        usage_store=usage, notifier=notifier, cache_ttl_seconds=60,
    )
    return gate, tenant, counters, subscriptions, plans


async def test_tenants_without_subscription_are_always_admitted_and_not_counted():
    gate, tenant, counters, _, _ = _gate(subscribed=False)

    decision = await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW)

    assert decision.allowed and decision.reason == "no_subscription"
    assert counters.counters == {}


async def test_counts_admitted_messages_and_refuses_past_a_hard_stop():
    notifier = FakeQuotaNotifier()
    gate, tenant, counters, _, _ = _gate(included=2, notifier=notifier)

    decisions = [await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW) for _ in range(4)]

    assert [d.allowed for d in decisions] == [True, True, False, False]
    assert counters.counters[(tenant, "2026-09")][WA] == 2
    # 80% crossed at msg 2 (2*100 >= 80*2), 100% at msg 2 too; blocked alert once.
    assert [a["event"] for a in notifier.alerts] == ["80", "100", "blocked"]


async def test_missing_counters_are_rebuilt_from_the_usage_archive():
    usage = FakeUsageStore()
    gate, tenant, counters, _, _ = _gate(included=5, usage=usage)
    for day in (1, 2, 3):
        await usage.insert_usage([UsageEvent(
            event_id=uuid4(), timestamp=datetime(2026, 9, day, tzinfo=timezone.utc), tenant_id=tenant,
            project_id=uuid4(), channel_type=WA, kind="platform", provider="flowsdone", sku="ai_message",
            quantity=Decimal(1), unit="message",
        )])
    # Usage from last month must not count.
    await usage.insert_usage([UsageEvent(
        event_id=uuid4(), timestamp=datetime(2026, 8, 31, tzinfo=timezone.utc), tenant_id=tenant,
        project_id=uuid4(), channel_type=WA, kind="platform", provider="flowsdone", sku="ai_message",
        quantity=Decimal(1), unit="message",
    )])

    decision = await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW)

    assert counters.seeded == [{WA: 3}]
    assert decision.used == 4


async def test_subscriptions_and_plans_are_cached_until_invalidated():
    gate, tenant, _, subscriptions, plans = _gate(included=100)

    for _ in range(3):
        await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW)
    assert (subscriptions.get_calls, plans.get_calls) == (1, 1)

    gate.invalidate(tenant)
    await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW)
    assert subscriptions.get_calls == 2


async def test_a_failing_notifier_never_breaks_the_decision():
    gate, tenant, _, _, _ = _gate(included=1, notifier=FakeQuotaNotifier(fail=True))

    decision = await gate.admit(tenant_id=tenant, channel_type=WA, now=NOW)

    assert decision.allowed
