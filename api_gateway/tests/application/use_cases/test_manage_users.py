"""Tests for UpdateUserUseCase and DeleteUserUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.manage_users import DeleteUserUseCase, SelfLockoutError, UpdateUserUseCase
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio


async def _setup(user=None):
    tenant = make_tenant()
    user = user or make_user(role="client", tenant_ids=[tenant.id])
    users, sessions = FakeUserRepo(), FakeAuthSessionRepo()
    users.add(user)
    token = await sessions.create(user.id, ttl_seconds=60)
    update = UpdateUserUseCase(user_repo=users, tenant_repo=FakeTenantRepo([tenant]), hasher=FakePasswordHasher(), sessions=sessions)
    delete = DeleteUserUseCase(user_repo=users, sessions=sessions)
    return update, delete, users, sessions, token, user, tenant


@pytest.mark.parametrize("change", [
    dict(role="botmaster"), dict(status="disabled"), dict(password="una-clave-larga-1"),
])
async def test_changes_that_affect_access_close_the_sessions(change):
    update, _, _, sessions, token, user, _ = await _setup()
    await update.execute(user.id, **change)
    assert token not in sessions.sessions


async def test_changing_the_tenants_closes_the_sessions():
    update, _, _, sessions, token, user, _ = await _setup()
    other = make_tenant(slug="other")
    update._tenants.tenants.append(other)
    await update.execute(user.id, tenant_ids=[other.id])
    assert token not in sessions.sessions


@pytest.mark.parametrize("change", [dict(name="Otro Nombre"), dict(status="active"), dict(role="client")])
async def test_harmless_or_identical_changes_keep_the_session(change):
    update, _, _, sessions, token, user, _ = await _setup()
    await update.execute(user.id, **change)
    assert token in sessions.sessions


async def test_resending_the_same_tenants_does_not_log_the_user_out():
    update, _, _, sessions, token, user, _ = await _setup()
    await update.execute(user.id, tenant_ids=list(user.tenant_ids))
    assert token in sessions.sessions


async def test_promoting_to_admin_drops_the_tenant_memberships():
    update, _, users, _, _, user, _ = await _setup()
    result = await update.execute(user.id, role="admin")
    assert result.role == "admin" and result.tenant_ids == []


async def test_demoting_an_admin_requires_a_tenant():
    admin = make_user(role="admin", tenant_ids=[])
    update, _, _, _, _, _, tenant = await _setup(admin)
    with pytest.raises(ValueError, match="at least one tenant"):
        await update.execute(admin.id, role="client")
    result = await update.execute(admin.id, role="client", tenant_ids=[tenant.id])
    assert result.role == "client" and result.tenant_ids == [tenant.id]


async def test_the_password_is_hashed_and_replaced():
    update, _, users, _, _, user, _ = await _setup()
    await update.execute(user.id, password="una-clave-larga-1")
    assert users.hashes[user.id] == "fake$una-clave-larga-1"


@pytest.mark.parametrize("change,message", [
    (dict(role="root"), "role must be"), (dict(status="banned"), "status must be"),
    (dict(name="  "), "name is required"), (dict(password="short"), "at least"),
    (dict(tenant_ids=[uuid4()]), "unknown tenant"),
])
async def test_invalid_updates_are_rejected_without_side_effects(change, message):
    update, _, users, sessions, token, user, _ = await _setup()
    before = users.users[user.id]
    with pytest.raises(ValueError, match=message):
        await update.execute(user.id, **change)
    assert users.users[user.id] == before and token in sessions.sessions


async def test_updating_an_unknown_user_returns_none():
    update, *_ = await _setup()
    assert await update.execute(uuid4(), name="x") is None


async def test_self_lockout_is_blocked_but_the_api_key_is_not_subject_to_it():
    admin = make_user(role="admin", tenant_ids=[])
    update, delete, *_ = await _setup(admin)
    for change in (dict(status="disabled"), dict(role="client")):
        with pytest.raises(SelfLockoutError):
            await update.execute(admin.id, actor_id=admin.id, **change)
    with pytest.raises(SelfLockoutError):
        await delete.execute(admin.id, actor_id=admin.id)
    assert (await update.execute(admin.id, actor_id=None, status="disabled")).status == "disabled"


async def test_delete_removes_the_user_and_closes_sessions():
    _, delete, users, sessions, token, user, _ = await _setup()
    assert await delete.execute(user.id, actor_id=uuid4()) is True
    assert user.id not in users.users and token not in sessions.sessions
    assert await delete.execute(user.id) is False
