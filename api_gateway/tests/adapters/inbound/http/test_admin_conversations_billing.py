"""HTTP tests for the conversations and billing admin API and /me/usage:
role matrix, tenant isolation and cost stripping for non-admins.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.inbound.http import me as me_module
from app.adapters.inbound.http.admin import billing as billing_module
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.models.usage import UsageEvent
from api_gateway.tests.support.admin_world import CSRF, World, cookie
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import make_cost_rate, make_plan, make_subscription

pytestmark = pytest.mark.anyio

BASE = "/internal/admin"
WA = "whatsapp_evolution"


@pytest.fixture
def world():
    return World.build()


async def _call(client, method, path, *, token, json=None):
    return await client.request(method, BASE + path, headers={**cookie(token), **CSRF}, json=json)


# ----------------------------------------------------------- conversations


async def test_conversations_are_listed_only_for_the_callers_tenants(world):
    async with world.client() as c:
        mine = await _call(c, "GET", "/conversations", token=await world.token("botmaster"))
        everything = await _call(c, "GET", "/conversations", token=await world.token("admin"))
        other = await _call(c, "GET", f"/conversations?tenant_id={world.tenant_b.id}", token=await world.token("tenant_manager"))
        client_role = await _call(c, "GET", "/conversations", token=await world.token("client"))

    assert [x["id"] for x in mine.json()] == [str(world.conversation_a.id)]
    assert {x["id"] for x in everything.json()} == {str(world.conversation_a.id), str(world.conversation_b.id)}
    assert other.status_code == 404
    assert client_role.status_code == 403


async def test_conversation_filters_are_passed_through(world):
    async with world.client() as c:
        resp = await _call(
            c, "GET", f"/conversations?status=open&channel_type=telegram&contact=600&limit=10&project_id={world.project_a.id}",
            token=await world.token("tenant_manager"),
        )
        bad_status = await _call(c, "GET", "/conversations?status=nope", token=await world.token("admin"))

    assert resp.status_code == 200
    call = world.conversations.list_calls[-1]
    assert (call["status"], call["channel_type"], call["contact"], call["limit"]) == ("open", "telegram", "600", 10)
    assert call["project_id"] == world.project_a.id
    assert bad_status.status_code == 422


async def test_conversation_detail_shows_costs_only_to_admins(world):
    conversation = world.conversation_a
    world.archived_messages.append(ConversationMessageRecorded(
        message_id=uuid4(), timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc), tenant_id=conversation.tenant_id,
        project_id=conversation.project_id, agent_id=conversation.agent_id, conversation_id=conversation.id,
        session_id=conversation.session_id, channel_type=conversation.channel_type,
        channel_connection_id=conversation.channel_connection_id, direction="inbound", sender_type="contact",
        app="langflow", contact=conversation.contact, text="hola",
    ))
    await world.usage.insert_usage([UsageEvent(
        event_id=uuid4(), timestamp=datetime(2026, 9, 1, tzinfo=timezone.utc), tenant_id=conversation.tenant_id,
        project_id=conversation.project_id, conversation_id=conversation.id, kind="llm", provider="openai",
        sku="gpt-4.1-mini", quantity=Decimal(1_000_000), unit="input_token",
    )])
    await world.cost_rates.create(make_cost_rate(price_micros=400_000))

    async with world.client() as c:
        admin = await _call(c, "GET", f"/conversations/{conversation.id}", token=await world.token("admin"))
        manager = await _call(c, "GET", f"/conversations/{conversation.id}", token=await world.token("tenant_manager"))
        other_tenant = await _call(c, "GET", f"/conversations/{world.conversation_b.id}", token=await world.token("tenant_manager"))
        missing = await _call(c, "GET", f"/conversations/{uuid4()}", token=await world.token("admin"))

    assert admin.status_code == 200
    body = admin.json()
    assert [m["text"] for m in body["messages"]] == ["hola"]
    assert body["cost_micros"] == 400_000 and body["usage"][0]["cost_micros"] == 400_000
    assert body["llm_input_tokens"] == 1_000_000
    assert manager.json()["cost_micros"] is None and manager.json()["usage"][0]["cost_micros"] is None
    assert other_tenant.status_code == missing.status_code == 404


# ------------------------------------------------------ plans / cost rates


@pytest.mark.parametrize("role", ["tenant_manager", "botmaster", "client"])
async def test_plans_and_cost_rates_are_admin_only(world, role):
    token = await world.token(role)
    async with world.client() as c:
        for method, path in (("GET", "/plans"), ("POST", "/plans"), ("GET", "/cost-rates"), ("GET", "/cost-rates/unrated")):
            resp = await _call(c, method, path, token=token, json={"code": "x", "name": "X"} if method == "POST" else None)
            assert resp.status_code == 403, path


async def test_plan_crud_with_duplicate_code_and_in_use_protection(world):
    token = await world.token("admin")
    body = {
        "code": "pro", "name": "Pro", "monthly_fee_micros": 49_000_000,
        "included_messages": {WA: 1000}, "overage_price_micros": {WA: 20_000},
        "margin_pct": "35", "default_overage_mode": "overage",
    }
    async with world.client() as c:
        created = await _call(c, "POST", "/plans", token=token, json=body)
        duplicate = await _call(c, "POST", "/plans", token=token, json=body)
        bad_code = await _call(c, "POST", "/plans", token=token, json={**body, "code": "Has Spaces"})
        plan_id = created.json()["id"]
        patched = await _call(c, "PATCH", f"/plans/{plan_id}", token=token, json={"monthly_fee_micros": 59_000_000})
        await _call(c, "PUT", f"/tenants/{world.tenant_a.id}/subscription", token=token, json={"plan_id": plan_id})
        listed = await _call(c, "GET", "/plans", token=token)
        in_use = await _call(c, "DELETE", f"/plans/{plan_id}", token=token)
        missing = await _call(c, "PATCH", f"/plans/{uuid4()}", token=token, json={"name": "x"})

    assert created.status_code == 201 and created.json()["margin_pct"] == "35"
    assert duplicate.status_code == 409 and bad_code.status_code == 422
    assert patched.json()["monthly_fee_micros"] == 59_000_000
    assert listed.json()[0]["subscriptions"] == 1
    assert in_use.status_code == 409 and missing.status_code == 404


async def test_cost_rates_versioning_and_unrated_meters(world, monkeypatch):
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(billing_module, "_now", lambda: now)
    await world.usage.insert_usage([UsageEvent(
        event_id=uuid4(), timestamp=now - timedelta(days=1), tenant_id=world.tenant_a.id, project_id=world.project_a.id,
        kind="llm", provider="openai", sku="gpt-5", quantity=Decimal(10), unit="output_token",
    )])
    token = await world.token("admin")
    async with world.client() as c:
        unrated_before = await _call(c, "GET", "/cost-rates/unrated", token=token)
        created = await _call(c, "POST", "/cost-rates", token=token, json={
            "kind": "llm", "provider": "openai", "sku": "gpt-5*", "unit": "output_token",
            "price_micros": 8_000_000, "per_quantity": 1_000_000, "valid_from": "2026-01-01T00:00:00Z",
        })
        unrated_after = await _call(c, "GET", "/cost-rates/unrated", token=token)
        rates = await _call(c, "GET", "/cost-rates", token=token)
        deleted = await _call(c, "DELETE", f"/cost-rates/{created.json()['id']}", token=token)
        deleted_again = await _call(c, "DELETE", f"/cost-rates/{created.json()['id']}", token=token)

    assert [m["sku"] for m in unrated_before.json()] == ["gpt-5"]
    assert created.status_code == 201 and unrated_after.json() == []
    assert len(rates.json()) == 1
    assert deleted.status_code == 204 and deleted_again.status_code == 404


async def test_pricing_insight_endpoint(world, monkeypatch):
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(billing_module, "_now", lambda: now)
    plan = await world.plans.create(make_plan(margin_pct=Decimal(20)))
    async with world.client() as c:
        ok = await _call(c, "GET", f"/plans/{plan.id}/pricing-insight?days=7", token=await world.token("admin"))
        missing = await _call(c, "GET", f"/plans/{uuid4()}/pricing-insight", token=await world.token("admin"))

    assert ok.status_code == 200 and ok.json()["days"] == 7 and ok.json()["sample"] == "platform"
    assert missing.status_code == 404


# ------------------------------------------- subscriptions and statements


async def test_only_admins_assign_plans_managers_read_their_tenants(world):
    plan = await world.plans.create(make_plan())
    inactive = await world.plans.create(make_plan(active=False))
    async with world.client() as c:
        by_manager = await _call(c, "PUT", f"/tenants/{world.tenant_a.id}/subscription",
                                 token=await world.token("tenant_manager"), json={"plan_id": str(plan.id)})
        admin_token = await world.token("admin")
        assigned = await _call(c, "PUT", f"/tenants/{world.tenant_a.id}/subscription", token=admin_token,
                               json={"plan_id": str(plan.id), "overage_mode": "hard_stop", "spending_cap_micros": 1000})
        to_inactive = await _call(c, "PUT", f"/tenants/{world.tenant_a.id}/subscription", token=admin_token,
                                  json={"plan_id": str(inactive.id)})
        read_by_manager = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/subscription",
                                      token=await world.token("tenant_manager"))
        other_tenant = await _call(c, "GET", f"/tenants/{world.tenant_b.id}/subscription",
                                   token=await world.token("tenant_manager"))
        none_yet = await _call(c, "GET", f"/tenants/{world.tenant_b.id}/subscription", token=admin_token)
        removed = await _call(c, "DELETE", f"/tenants/{world.tenant_a.id}/subscription", token=admin_token)

    assert by_manager.status_code == 403
    assert assigned.status_code == 200 and assigned.json()["effective_overage_mode"] == "hard_stop"
    assert to_inactive.status_code == 400
    assert read_by_manager.status_code == 200 and read_by_manager.json()["plan_code"] == plan.code
    assert other_tenant.status_code == 404 and none_yet.status_code == 404
    assert removed.status_code == 204


async def test_statement_strips_costs_for_managers_and_closing_is_admin_only(world, monkeypatch):
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(billing_module, "_now", lambda: now)
    plan = await world.plans.create(make_plan(included_messages={WA: 1}, overage_price_micros={WA: 100_000}))
    await world.subscriptions.upsert(make_subscription(tenant_id=world.tenant_a.id, plan_id=plan.id))
    day = datetime(2026, 9, 10, tzinfo=timezone.utc)
    await world.usage.insert_usage([
        UsageEvent(event_id=uuid4(), timestamp=day, tenant_id=world.tenant_a.id, project_id=world.project_a.id,
                   channel_type=WA, kind="platform", provider="flowsdone", sku="ai_message", quantity=Decimal(1), unit="message")
        for _ in range(3)
    ])
    async with world.client() as c:
        admin_token = await world.token("admin")
        as_admin = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/statement?period=2026-09", token=admin_token)
        as_manager = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/statement?period=2026-09",
                                 token=await world.token("tenant_manager"))
        bad_period = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/statement?period=2026-13", token=admin_token)
        close_by_manager = await _call(c, "POST", "/billing/periods/2026-09/close", token=await world.token("tenant_manager"))
        closed = await _call(c, "POST", "/billing/periods/2026-09/close", token=admin_token)
        not_over = await _call(c, "POST", "/billing/periods/2026-10/close", token=admin_token)
        history = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/statements", token=admin_token)

    assert as_admin.json()["cost_micros"] == 0 and as_admin.json()["costs"] is not None
    manager = as_manager.json()
    assert manager["revenue_micros"] == plan.monthly_fee_micros + 200_000
    assert manager["cost_micros"] is None and manager["margin_micros"] is None and manager["costs"] is None
    assert manager["channels"][0]["cost_micros"] is None
    assert bad_period.status_code == 422
    assert close_by_manager.status_code == 403
    assert closed.json() == {"period": "2026-09", "closed": 1}
    assert not_over.status_code == 400
    assert [s["status"] for s in history.json()] == ["closed"]


async def test_me_usage_is_for_clients_and_never_shows_costs(world):
    plan = await world.plans.create(make_plan())
    await world.subscriptions.upsert(make_subscription(tenant_id=world.tenant_a.id, plan_id=plan.id))
    state = {**world.state()}

    async with client_for_router(me_module.router, **state) as c:
        client_resp = await c.get("/me/usage", headers=cookie(await world.token("client")))
        consultant = await c.get("/me/usage", headers=cookie(await world.token("consultant")))
        bad = await c.get("/me/usage?period=junk", headers=cookie(await world.token("client")))

    assert client_resp.status_code == 200
    body = client_resp.json()
    assert body["plan_name"] == plan.name and body["tenant_id"] == str(world.tenant_a.id)
    assert body["cost_micros"] is None and body["costs"] is None
    assert consultant.status_code == 403 and bad.status_code == 422
