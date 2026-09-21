"""Tests for GetCurrentUserUseCase and LogoutUserUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.logout_user import LogoutUserUseCase
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio


async def _setup(user):
    users, sessions = FakeUserRepo(), FakeAuthSessionRepo()
    users.add(user)
    token = await sessions.create(user.id, ttl_seconds=10)
    tenant = make_tenant()
    use_case = GetCurrentUserUseCase(
        sessions=sessions,
        user_repo=users,
        tenant_repo=FakeTenantRepo([tenant]),
        session_ttl_seconds=3600,
    )
    return use_case, users, sessions, token, tenant


async def test_valid_token_returns_the_user_and_slides_the_session():
    tenant = make_tenant()
    user = make_user(role="tenant_manager", tenant_ids=[tenant.id])
    users, sessions = FakeUserRepo(), FakeAuthSessionRepo()
    users.add(user)
    token = await sessions.create(user.id, ttl_seconds=10)
    use_case = GetCurrentUserUseCase(
        sessions=sessions, user_repo=users, tenant_repo=FakeTenantRepo([tenant]), session_ttl_seconds=3600
    )

    result = await use_case.execute(token)

    assert result.id == user.id
    assert [t.id for t in result.tenants] == [tenant.id]
    assert sessions.ttls[token] == 3600


@pytest.mark.parametrize("token", [None, "", "unknown-token"])
async def test_missing_or_unknown_token_returns_none(token):
    use_case, *_ = await _setup(make_user())
    assert await use_case.execute(token) is None


async def test_disabled_user_loses_the_session_immediately():
    user = make_user()
    use_case, users, sessions, token, _ = await _setup(user)
    users.users[user.id] = make_user(id=user.id, email=user.email, status="disabled")

    assert await use_case.execute(token) is None
    assert token not in sessions.sessions  # la sesión huérfana se cierra


async def test_deleted_user_returns_none_and_closes_the_session():
    user = make_user()
    use_case, users, sessions, token, _ = await _setup(user)
    del users.users[user.id]

    assert await use_case.execute(token) is None
    assert token not in sessions.sessions


async def test_role_changes_apply_on_the_next_request():
    user = make_user(role="client")
    use_case, users, _, token, _ = await _setup(user)
    users.users[user.id] = make_user(id=user.id, email=user.email, role="admin")

    assert (await use_case.execute(token)).role == "admin"


async def test_logout_closes_the_session_and_ignores_missing_tokens():
    sessions = FakeAuthSessionRepo()
    user = make_user()
    token = await sessions.create(user.id, ttl_seconds=10)
    use_case = LogoutUserUseCase(sessions=sessions)

    await use_case.execute(token)
    await use_case.execute(token)
    await use_case.execute(None)

    assert sessions.sessions == {}
