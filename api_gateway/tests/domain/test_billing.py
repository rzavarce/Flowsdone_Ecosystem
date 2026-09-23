"""Tests for plans, quota decisions, statements and pricing insight."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.models.billing import (
    build_statement,
    evaluate_quota,
    month_bounds,
    overage_spend,
    period_of,
    previous_period,
    pricing_insight,
)
from app.domain.models.usage import RatedUsage, UsageAggregate
from api_gateway.tests.support.fakes import make_cost_rate, make_plan, make_subscription

WA = "whatsapp_evolution"
NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _plan(**overrides):
    fields = {"included_messages": {WA: 10, "*": 2}, "overage_price_micros": {WA: 50_000}, **overrides}
    return make_plan(**fields)


def test_plan_allowances_fall_back_to_the_wildcard():
    plan = _plan()

    assert plan.included_for(WA) == 10
    assert plan.included_for("telegram") == 2
    assert plan.overage_price_for(WA) == 50_000
    assert plan.overage_price_for("telegram") is None
    assert make_plan(included_messages={}).included_for(WA) == 0


def test_allowed_models():
    assert make_plan().allows_model("anything")
    plan = make_plan(allowed_models=["gpt-4.1-mini*", "claude-haiku-4-5"])
    assert plan.allows_model("gpt-4.1-mini-2025")
    assert plan.allows_model("claude-haiku-4-5")
    assert not plan.allows_model("gpt-4.1")


def test_within_quota_is_allowed_and_crosses_thresholds_once():
    plan = _plan()
    subscription = make_subscription(plan_id=plan.id)

    at_7 = evaluate_quota(plan, subscription, WA, {WA: 7})
    at_8 = evaluate_quota(plan, subscription, WA, {WA: 8})
    at_10 = evaluate_quota(plan, subscription, WA, {WA: 9})

    assert at_7.allowed and at_7.reason == "within_quota" and at_7.thresholds_crossed == (80,)
    assert at_8.thresholds_crossed == ()
    assert at_10.thresholds_crossed == (100,) and at_10.used == 10


@pytest.mark.parametrize("mode,allowed,reason", [
    ("notify", True, "notify"),
    ("overage", True, "overage"),
    ("hard_stop", False, "hard_stop"),
])
def test_past_the_quota_depends_on_the_mode(mode, allowed, reason):
    plan = _plan(default_overage_mode=mode)

    decision = evaluate_quota(plan, make_subscription(plan_id=plan.id), WA, {WA: 10})

    assert (decision.allowed, decision.reason) == (allowed, reason)
    assert decision.used == (11 if allowed else 10)


def test_the_subscription_overrides_the_plan_mode():
    plan = _plan(default_overage_mode="notify")

    decision = evaluate_quota(plan, make_subscription(plan_id=plan.id, overage_mode="hard_stop"), WA, {WA: 10})

    assert not decision.allowed


def test_spending_cap_refuses_once_exceeded_across_channels():
    plan = _plan(default_overage_mode="overage", overage_price_micros={WA: 50_000, "*": 10_000})
    subscription = make_subscription(plan_id=plan.id, spending_cap_micros=200_000)
    # telegram: 2 over -> 20_000; whatsapp: 3 over -> 150_000 => 170_000 spent
    used = {WA: 13, "telegram": 4}

    assert overage_spend(plan, used) == 170_000
    refused = evaluate_quota(plan, subscription, WA, used)  # +50_000 -> 220_000 > cap
    allowed = evaluate_quota(plan, subscription, "telegram", used)  # +10_000 -> 180_000

    assert (refused.allowed, refused.reason) == (False, "spending_cap")
    assert refused.overage_spend_micros == 170_000
    assert allowed.allowed and allowed.overage_spend_micros == 180_000


def test_periods():
    assert month_bounds("2026-12") == (
        datetime(2026, 12, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    assert period_of(NOW) == "2026-09"
    assert previous_period(date(2026, 1, 15)) == "2025-12"
    assert previous_period(date(2026, 9, 1)) == "2026-08"
    with pytest.raises(ValueError):
        month_bounds("sept")


def _rated(kind, provider, sku, unit, quantity, cost, channel=WA, rated=True):
    usage = UsageAggregate(
        day=date(2026, 9, 1), tenant_id=uuid4(), kind=kind, provider=provider, channel_type=channel,
        sku=sku, unit=unit, quantity=Decimal(quantity),
    )
    return RatedUsage(usage=usage, rate=make_cost_rate() if rated else None, cost_micros=cost)


def test_statement_charges_fee_and_overage_and_reports_costs_and_margin():
    plan = _plan(monthly_token_allowance=1000, allowed_models=["gpt-4.1-mini*"])
    tenant = uuid4()
    rated = [
        _rated("platform", "flowsdone", "ai_message", "message", 15, 0),
        _rated("channel", WA, "message.inbound", "message", 15, 0),
        _rated("llm", "openai", "gpt-4.1-mini", "input_token", 900, 360),
        _rated("llm", "openai", "gpt-4.1", "output_token", 200, 1600),
        _rated("llm", "openai", "gpt-4.1", "cached_input_token", 50, 0, rated=False),
    ]

    statement = build_statement(
        tenant_id=tenant, period="2026-09", rated=rated, plan=plan,
        subscription=make_subscription(tenant_id=tenant, plan_id=plan.id), now=NOW,
    )

    [line] = statement.channels
    assert (line.messages, line.included, line.overage_messages, line.overage_amount_micros) == (15, 10, 5, 250_000)
    assert line.cost_micros == 1960
    assert statement.revenue_micros == plan.monthly_fee_micros + 250_000
    assert statement.cost_micros == 1960
    assert statement.margin_micros == statement.revenue_micros - 1960
    assert statement.llm_input_tokens == 900 and statement.llm_output_tokens == 200
    assert statement.llm_cached_input_tokens == 50
    assert statement.over_token_allowance is True
    assert statement.disallowed_models == ["gpt-4.1"]
    assert statement.unrated_meters == 1
    assert statement.overage_mode == "notify"


def test_statement_without_plan_charges_nothing_but_reports_cost():
    statement = build_statement(
        tenant_id=uuid4(), period="2026-09", now=NOW, plan=None, subscription=None,
        rated=[_rated("platform", "flowsdone", "ai_message", "message", 3, 0), _rated("llm", "openai", "m", "input_token", 10, 99)],
    )

    assert statement.revenue_micros == 0 and statement.cost_micros == 99
    assert statement.margin_pct is None
    assert statement.channels[0].overage_messages == 0


def test_pricing_insight_suggests_cost_plus_margin():
    plan = _plan(margin_pct=Decimal(50), overage_price_micros={WA: 3000})
    rated = [
        _rated("platform", "flowsdone", "ai_message", "message", 100, 0),
        _rated("channel", WA, "message.outbound", "message", 100, 0),
        _rated("llm", "openai", "m", "input_token", 1, 200_000),
    ]

    [wa] = [c for c in pricing_insight(plan, rated) if c.channel_type == WA]

    assert wa.messages == 100 and wa.avg_cost_micros == 2000
    assert wa.suggested_price_micros == 3000
    assert wa.configured_price_micros == 3000
    assert wa.margin_at_configured_pct == Decimal("50.0")


def test_pricing_insight_without_usage_has_no_suggestion():
    [only] = pricing_insight(make_plan(included_messages={"telegram": 5}, overage_price_micros={}), [])

    assert only.channel_type == "telegram" and only.avg_cost_micros is None and only.suggested_price_micros is None
