"""Integration tests for the plan, subscription, statement and
conversation-listing repositories against a real, migrated, throwaway
Postgres (TEST_POSTGRES_URL)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.billing_repositories import (
    SqlAlchemyPlanRepository,
    SqlAlchemyStatementRepository,
    SqlAlchemySubscriptionRepository,
)
from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.domain.models.billing import BillingStatement
from app.domain.ports.outbound import AlreadyExistsError, PlanInUseError
from app.infrastructure.database import create_sessionmaker
from api_gateway.tests.support.fakes import make_conversation, make_plan, make_subscription

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture
async def ctx():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    tenant_id, project_id = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, status) VALUES (:id, 'it', :slug, 'active')"),
            {"id": tenant_id, "slug": f"it-{tenant_id}"},
        )
        await conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, slug, status) VALUES (:id, :t, 'it', :slug, 'active')"),
            {"id": project_id, "t": tenant_id, "slug": f"it-{project_id}"},
        )
    sessionmaker = create_sessionmaker(engine)
    created_plans = []
    yield dict(sessionmaker=sessionmaker, tenant_id=tenant_id, project_id=project_id, plans=created_plans)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        for plan_id in created_plans:
            await conn.execute(text("DELETE FROM plans WHERE id = :id"), {"id": plan_id})
    await engine.dispose()


async def test_plans_roundtrip_json_fields_and_unique_code(ctx):
    repo = SqlAlchemyPlanRepository(ctx["sessionmaker"])
    plan = make_plan(
        code=f"it-{uuid.uuid4().hex[:8]}", included_messages={"telegram": 10, "*": 5},
        allowed_models=["gpt-4.1-mini*"], margin_pct=Decimal("32.5"), monthly_token_allowance=1_000_000,
    )
    ctx["plans"].append(plan.id)

    stored = await repo.create(plan)
    with pytest.raises(AlreadyExistsError):
        await repo.create(make_plan(code=plan.code))
    updated = await repo.update(plan.id, name="Pro+", included_messages={"telegram": 20})

    assert stored.included_messages == {"telegram": 10, "*": 5}
    assert stored.margin_pct == Decimal("32.50") and stored.allowed_models == ["gpt-4.1-mini*"]
    assert updated.name == "Pro+" and updated.included_messages == {"telegram": 20}
    assert await repo.update(uuid.uuid4(), name="x") is None
    assert plan.id in {p.id for p in await repo.list_all()}


async def test_subscription_upsert_and_plan_in_use(ctx):
    plans = SqlAlchemyPlanRepository(ctx["sessionmaker"])
    subscriptions = SqlAlchemySubscriptionRepository(ctx["sessionmaker"])
    plan = await plans.create(make_plan(code=f"it-{uuid.uuid4().hex[:8]}"))
    other = await plans.create(make_plan(code=f"it-{uuid.uuid4().hex[:8]}"))
    ctx["plans"].extend([plan.id, other.id])

    await subscriptions.upsert(make_subscription(tenant_id=ctx["tenant_id"], plan_id=plan.id))
    replaced = await subscriptions.upsert(
        make_subscription(tenant_id=ctx["tenant_id"], plan_id=other.id, overage_mode="overage", spending_cap_micros=5)
    )

    assert replaced.plan_id == other.id and replaced.overage_mode == "overage"
    assert (await subscriptions.get(ctx["tenant_id"])).spending_cap_micros == 5
    with pytest.raises(PlanInUseError):
        await plans.delete(other.id)
    assert await plans.delete(plan.id) is True
    assert await subscriptions.delete(ctx["tenant_id"]) is True
    assert await subscriptions.get(ctx["tenant_id"]) is None


async def test_statements_are_frozen_once(ctx):
    repo = SqlAlchemyStatementRepository(ctx["sessionmaker"])
    statement = BillingStatement(
        tenant_id=ctx["tenant_id"], period="2026-08", status="closed", revenue_micros=10, cost_micros=3,
        margin_pct=Decimal("70.0"), generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    assert await repo.save_closed(statement) is True
    assert await repo.save_closed(statement.model_copy(update={"revenue_micros": 999})) is False
    stored = await repo.get(ctx["tenant_id"], "2026-08")
    assert stored.revenue_micros == 10 and stored.margin_pct == Decimal("70.0")
    assert [s.period for s in await repo.list_by_tenant(ctx["tenant_id"])] == ["2026-08"]


async def test_conversation_listing_filters_and_paginates(ctx):
    repo = SqlAlchemyConversationRepository(ctx["sessionmaker"])
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    for i, (channel, contact) in enumerate([("telegram", "+34 600 1"), ("voice", "+34 600 2"), ("telegram", "50%_off")]):
        await repo.open(make_conversation(
            tenant_id=ctx["tenant_id"], project_id=ctx["project_id"], channel_type=channel, contact=contact,
            started_at=t0, last_inbound_at=t0, last_message_at=t0 + timedelta(hours=i),
        ))

    newest_first = await repo.list(tenant_ids=[ctx["tenant_id"]])
    telegram = await repo.list(tenant_ids=[ctx["tenant_id"]], channel_type="telegram")
    page2 = await repo.list(tenant_ids=[ctx["tenant_id"]], before=newest_first[0].last_message_at, limit=1)
    literal = await repo.list(tenant_ids=[ctx["tenant_id"]], contact="%_")

    assert [c.contact for c in newest_first] == ["50%_off", "+34 600 2", "+34 600 1"]
    assert {c.channel_type for c in telegram} == {"telegram"} and len(telegram) == 2
    assert [c.contact for c in page2] == ["+34 600 2"]
    assert [c.contact for c in literal] == ["50%_off"]
    assert await repo.list(tenant_ids=[]) == []
