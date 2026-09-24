"""Tests for DeleteTenantUseCase (tenant + client accounts + Langflow user)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.delete_tenant import DeleteTenantUseCase
from app.application.use_cases.manage_users import DeleteUserUseCase
from app.domain.ports.outbound import LangflowSessionError
from api_gateway.tests.application.use_cases.test_langflow_sso import World
from api_gateway.tests.support.fakes import FakeAuthSessionRepo, FakeUserRepo, make_tenant, make_user

pytestmark = pytest.mark.anyio


def _setup():
    w = World()
    users = FakeUserRepo()
    use_case = DeleteTenantUseCase(
        tenant_repo=w.tenants, user_repo=users,
        delete_user=DeleteUserUseCase(user_repo=users, sessions=FakeAuthSessionRepo()),
        accounts=w.accounts, langflow=w.langflow,
    )
    return w, users, use_case


async def test_deletes_the_tenant_its_client_account_and_its_langflow_user():
    w, users, use_case = _setup()
    await w.add_project("Soporte")
    await w.prepare.open_workspace(w.tenant.id)  # provisions the Langflow user
    client = users.add(make_user(role="client", email="c@acme.com", tenant_ids=[w.tenant.id]))
    other = make_tenant(slug="otro")
    shared_client = users.add(make_user(role="client", email="s@x.com", tenant_ids=[w.tenant.id, other.id]))
    staff = users.add(make_user(role="botmaster", email="b@x.com", tenant_ids=[w.tenant.id]))

    assert await use_case.execute(w.tenant.id) is True

    assert w.langflow.deleted_users == ["lf-tenant-acme"]
    remaining = {u.id for u in await users.list()}
    assert client.id not in remaining  # its email can be used again
    assert {shared_client.id, staff.id} <= remaining
    assert await w.tenants.get_by_id(w.tenant.id) is None


async def test_a_tenant_that_never_opened_langflow_does_not_touch_it():
    w, _, use_case = _setup()

    assert await use_case.execute(w.tenant.id) is True
    assert "delete_user" not in w.langflow.calls


async def test_if_langflow_fails_nothing_is_deleted():
    w, users, use_case = _setup()
    await w.prepare.open_workspace(w.tenant.id)
    client = users.add(make_user(role="client", email="c@acme.com", tenant_ids=[w.tenant.id]))

    async def boom(langflow_user_id):
        raise LangflowSessionError("down")

    w.langflow.delete_user = boom
    with pytest.raises(LangflowSessionError):
        await use_case.execute(w.tenant.id)
    assert await w.tenants.get_by_id(w.tenant.id) is not None
    assert await users.get_by_id(client.id) is not None


async def test_an_unknown_tenant_is_not_deleted():
    _, _, use_case = _setup()
    assert await use_case.execute(uuid4()) is False
