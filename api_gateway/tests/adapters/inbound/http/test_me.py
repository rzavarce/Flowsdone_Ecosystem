"""HTTP tests for the self-service `/me/*` endpoints."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.me import router
from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.core.config import settings
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakeTenantBillingProfileRepo,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio


def _state(users=(), tenants=()):
    user_repo = FakeUserRepo()
    for u in users:
        user_repo.add(u)
    tenant_repo = FakeTenantRepo(list(tenants))
    sessions = FakeAuthSessionRepo()
    billing = FakeTenantBillingProfileRepo()
    return dict(
        sessions=sessions,
        billing=billing,
        get_current_user_use_case=GetCurrentUserUseCase(
            sessions=sessions, user_repo=user_repo, tenant_repo=tenant_repo, session_ttl_seconds=3600
        ),
        tenant_billing_profile_repo=billing,
    )


def _cookie(token):
    return {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}"}


async def test_returns_the_callers_own_tenant_billing_profile():
    tenant = make_tenant()
    client_user = make_user(role="client", tenant_ids=[tenant.id])
    state = _state([client_user], [tenant])
    await state["billing"].upsert(tenant.id, legal_name="Acme Corp S.A.", currency="USD")
    token = await state["sessions"].create(client_user.id, ttl_seconds=3600)

    async with client_for_router(router, **state) as client:
        resp = await client.get("/me/billing-profile", headers=_cookie(token))

    assert resp.status_code == 200
    assert resp.json()["legal_name"] == "Acme Corp S.A."
    assert resp.json()["tenant_id"] == str(tenant.id)


async def test_404_without_a_profile_yet_or_without_a_session():
    tenant = make_tenant()
    client_user = make_user(role="client", tenant_ids=[tenant.id])
    state = _state([client_user], [tenant])
    token = await state["sessions"].create(client_user.id, ttl_seconds=3600)

    async with client_for_router(router, **state) as client:
        no_profile = await client.get("/me/billing-profile", headers=_cookie(token))
        no_session = await client.get("/me/billing-profile")

    assert no_profile.status_code == 404
    assert no_session.status_code == 401


async def test_404_for_a_user_with_no_tenant():
    admin = make_user(role="admin", tenant_ids=[])
    state = _state([admin])
    token = await state["sessions"].create(admin.id, ttl_seconds=3600)

    async with client_for_router(router, **state) as client:
        resp = await client.get("/me/billing-profile", headers=_cookie(token))

    assert resp.status_code == 404


async def test_never_reveals_another_tenants_billing_profile():
    mine, other = make_tenant(slug="mine"), make_tenant(slug="other")
    consultant = make_user(role="consultant", email="c@x.com", tenant_ids=[mine.id])
    state = _state([consultant], [mine, other])
    await state["billing"].upsert(other.id, legal_name="Otro Cliente")
    token = await state["sessions"].create(consultant.id, ttl_seconds=3600)

    async with client_for_router(router, **state) as client:
        resp = await client.get("/me/billing-profile", headers=_cookie(token))

    # No hay perfil para "mine" (solo se cargó el de "other"): 404, nunca el ajeno.
    assert resp.status_code == 404
