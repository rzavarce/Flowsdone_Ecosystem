"""Tests for the billing use cases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.use_cases.billing import (
    CloseBillingPeriodUseCase,
    ComputeStatementUseCase,
    ListUnratedMetersUseCase,
    PlanNotFoundError,
    PlanPricingInsightUseCase,
)
from app.domain.models.usage import UsageEvent
from api_gateway.tests.support.fakes import (
    FakeCostRateRepo,
    FakePlanRepo,
    FakeStatementRepo,
    FakeSubscriptionRepo,
    FakeUsageStore,
    make_cost_rate,
    make_plan,
    make_subscription,
)

pytestmark = pytest.mark.anyio

WA = "whatsapp_evolution"


def _event(tenant, when, kind, provider, sku, unit, quantity, channel=WA):
    return UsageEvent(
        event_id=uuid4(), timestamp=when, tenant_id=tenant, project_id=uuid4(), channel_type=channel,
        kind=kind, provider=provider, sku=sku, quantity=Decimal(quantity), unit=unit,
    )


async def _world(now):
    plan = make_plan(included_messages={WA: 2}, overage_price_micros={WA: 100_000}, margin_pct=Decimal(100))
    tenant = uuid4()
    usage = FakeUsageStore()
    day = datetime(2026, 9, 5, tzinfo=timezone.utc)
    await usage.insert_usage(
        [_event(tenant, day, "platform", "flowsdone", "ai_message", "message", 1) for _ in range(3)]
        + [_event(tenant, day, "llm", "openai", "gpt-4.1-mini", "input_token", 1_000_000)]
        + [_event(tenant, day, "llm", "openai", "mystery-model", "output_token", 10)]
    )
    rates = FakeCostRateRepo(make_cost_rate(sku="gpt-4.1-mini*", unit="input_token", price_micros=300_000))
    subscriptions = FakeSubscriptionRepo(make_subscription(tenant_id=tenant, plan_id=plan.id))
    statements = FakeStatementRepo()
    compute = ComputeStatementUseCase(
        usage_store=usage, cost_rates=rates, plans=FakePlanRepo(plan), subscriptions=subscriptions, statements=statements
    )
    return dict(plan=plan, tenant=tenant, usage=usage, rates=rates, subscriptions=subscriptions,
                statements=statements, compute=compute)


async def test_preview_rates_the_month_usage_against_the_plan():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    w = await _world(now)

    statement = await w["compute"].execute(tenant_id=w["tenant"], period="2026-09", now=now)

    assert statement.status == "preview"
    [line] = statement.channels
    assert (line.messages, line.overage_messages, line.overage_amount_micros) == (3, 1, 100_000)
    assert statement.cost_micros == 300_000
    assert statement.unrated_meters == 1


async def test_closing_freezes_statements_and_is_idempotent():
    now = datetime(2026, 10, 1, 7, tzinfo=timezone.utc)
    w = await _world(now)
    close = CloseBillingPeriodUseCase(compute=w["compute"], subscriptions=w["subscriptions"], statements=w["statements"])

    assert await close.execute(period="2026-09", now=now) == 1
    assert await close.execute(period="2026-09", now=now) == 0

    # A rate added later changes previews, not the closed statement.
    await w["rates"].create(make_cost_rate(sku="mystery*", unit="output_token", price_micros=1_000_000, per_quantity=1))
    closed = await w["compute"].execute(tenant_id=w["tenant"], period="2026-09", now=now)
    preview = await w["compute"].preview(tenant_id=w["tenant"], period="2026-09", now=now)
    assert closed.status == "closed" and closed.cost_micros == 300_000
    assert preview.cost_micros == 300_000 + 10_000_000


async def test_a_period_cannot_be_closed_before_its_grace_period():
    w = await _world(None)
    close = CloseBillingPeriodUseCase(compute=w["compute"], subscriptions=w["subscriptions"], statements=w["statements"])

    assert close.closable_at("2026-09") == datetime(2026, 10, 1, 6, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        await close.execute(period="2026-09", now=datetime(2026, 10, 1, 5, tzinfo=timezone.utc))


async def test_pricing_insight_uses_the_plan_tenants_or_falls_back_to_the_platform():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    w = await _world(now)
    plans = FakePlanRepo(w["plan"])
    other_plan = make_plan(included_messages={WA: 1})
    plans.plans[other_plan.id] = other_plan
    use_case = PlanPricingInsightUseCase(usage_store=w["usage"], cost_rates=w["rates"], plans=plans, subscriptions=w["subscriptions"])

    own = await use_case.execute(plan_id=w["plan"].id, now=now)
    fallback = await use_case.execute(plan_id=other_plan.id, now=now)

    [wa] = own.channels
    assert own.sample == "plan" and wa.messages == 3 and wa.avg_cost_micros == 100_000
    assert wa.suggested_price_micros == 200_000  # margin 100%
    assert fallback.sample == "platform"
    with pytest.raises(PlanNotFoundError):
        await use_case.execute(plan_id=uuid4(), now=now)


async def test_unrated_meters_are_listed():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    w = await _world(now)

    [meter] = await ListUnratedMetersUseCase(usage_store=w["usage"], cost_rates=w["rates"]).execute(now=now)

    assert (meter.sku, meter.unit, meter.quantity) == ("mystery-model", "output_token", Decimal(10))
