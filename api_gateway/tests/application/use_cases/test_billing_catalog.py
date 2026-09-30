"""Tests for ManageBillingCatalogUseCase: the rules behind plans and subscriptions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.application.use_cases.billing_catalog import InactivePlanError, ManageBillingCatalogUseCase
from api_gateway.tests.support.fakes import (
    FakeCostRateRepo,
    FakePlanRepo,
    FakeStatementRepo,
    FakeSubscriptionRepo,
    make_plan,
    make_subscription,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)


class FakeTenants:
    def __init__(self, *ids):
        self.ids = set(ids)

    async def get_by_id(self, tenant_id):
        return object() if tenant_id in self.ids else None


class FakeQuotaGate:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, tenant_id=None):
        self.invalidated.append(tenant_id)


def _catalog(*, plans=(), subscriptions=(), tenants=()):
    gate = FakeQuotaGate()
    use_case = ManageBillingCatalogUseCase(
        plans=FakePlanRepo(*plans),
        subscriptions=FakeSubscriptionRepo(*subscriptions),
        cost_rates=FakeCostRateRepo(),
        statements=FakeStatementRepo(),
        tenants=FakeTenants(*tenants),
        quota_gate=gate,
    )
    return use_case, gate


async def test_plans_come_with_their_subscriber_count():
    pro, starter = make_plan(code="pro"), make_plan(code="starter")
    use_case, _ = _catalog(
        plans=[pro, starter],
        subscriptions=[make_subscription(plan_id=pro.id), make_subscription(plan_id=pro.id)],
    )

    counts = {item.plan.code: item.subscribers for item in await use_case.list_plans()}

    assert counts == {"pro": 2, "starter": 0}


async def test_subscribing_needs_an_active_plan():
    inactive = make_plan(active=False)
    use_case, gate = _catalog(plans=[inactive])

    for plan_id in (inactive.id, uuid4()):
        with pytest.raises(InactivePlanError):
            await use_case.subscribe(uuid4(), plan_id=plan_id, overage_mode=None, spending_cap_micros=None, now=NOW)
    assert gate.invalidated == []


async def test_changing_plan_keeps_the_start_date_and_refreshes_the_quota():
    old, new = make_plan(), make_plan()
    tenant = uuid4()
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    use_case, gate = _catalog(plans=[old, new], subscriptions=[make_subscription(tenant_id=tenant, plan_id=old.id, started_at=started)])

    subscription, plan = await use_case.subscribe(tenant, plan_id=new.id, overage_mode="notify", spending_cap_micros=None, now=NOW)

    assert plan.id == new.id and subscription.plan_id == new.id
    assert subscription.started_at == started
    assert gate.invalidated == [tenant]


async def test_a_new_subscription_starts_now():
    plan = make_plan()
    use_case, _ = _catalog(plans=[plan])

    subscription, _ = await use_case.subscribe(uuid4(), plan_id=plan.id, overage_mode=None, spending_cap_micros=None, now=NOW)

    assert subscription.started_at == NOW


async def test_editing_a_plan_refreshes_every_quota_and_unknown_plans_are_none():
    plan = make_plan(name="Pro")
    use_case, gate = _catalog(plans=[plan])

    item = await use_case.update_plan(plan.id, {"name": "Pro+"})

    assert item.plan.name == "Pro+" and gate.invalidated == [None]
    assert await use_case.update_plan(uuid4(), {"name": "x"}) is None


async def test_unsubscribing_refreshes_the_quota_only_if_there_was_one():
    tenant = uuid4()
    use_case, gate = _catalog(subscriptions=[make_subscription(tenant_id=tenant)])

    assert await use_case.unsubscribe(tenant) is True
    assert await use_case.unsubscribe(tenant) is False
    assert gate.invalidated == [tenant]


async def test_tenant_existence():
    tenant = uuid4()
    use_case, _ = _catalog(tenants=[tenant])

    assert await use_case.tenant_exists(tenant) is True
    assert await use_case.tenant_exists(uuid4()) is False
