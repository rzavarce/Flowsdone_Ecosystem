"""Tests for ResetPasswordUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.activate_account import InvalidTokenError
from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH
from app.application.use_cases.reset_password import ResetPasswordUseCase
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeAuthSessionRepo,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_user,
)

pytestmark = pytest.mark.anyio

NEW_PASSWORD = "y" * MIN_PASSWORD_LENGTH
OLD_PASSWORD = "correct-horse-battery"


def _build(*, user):
    users = FakeUserRepo()
    users.add(user, OLD_PASSWORD)
    tokens = FakeAccountTokenStore()
    sessions = FakeAuthSessionRepo()
    use_case = ResetPasswordUseCase(
        tokens=tokens,
        user_repo=users,
        tenant_repo=FakeTenantRepo(),
        hasher=FakePasswordHasher(),
        sessions=sessions,
        session_ttl_seconds=3600,
    )
    return use_case, users, tokens, sessions


async def test_resets_the_password_and_opens_a_new_session():
    user = make_user(status="active")
    use_case, users, tokens, sessions = _build(user=user)
    token = await tokens.issue(user.id, ttl_seconds=3600)

    session_token, result = await use_case.execute(token=token, password=NEW_PASSWORD)

    assert result.id == user.id
    assert users.hashes[user.id] == f"fake${NEW_PASSWORD}"
    assert sessions.sessions[session_token] == user.id


async def test_closes_previous_sessions_so_a_stolen_one_stops_working():
    user = make_user(status="active")
    use_case, users, tokens, sessions = _build(user=user)
    old_session = await sessions.create(user.id, ttl_seconds=3600)
    token = await tokens.issue(user.id, ttl_seconds=3600)

    await use_case.execute(token=token, password=NEW_PASSWORD)

    assert old_session not in sessions.sessions


async def test_the_token_can_only_be_used_once():
    user = make_user(status="active")
    use_case, _, tokens, _ = _build(user=user)
    token = await tokens.issue(user.id, ttl_seconds=3600)
    await use_case.execute(token=token, password=NEW_PASSWORD)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_unknown_or_expired_token_is_rejected():
    use_case, *_ = _build(user=make_user())
    with pytest.raises(InvalidTokenError):
        await use_case.execute(token="nope", password=NEW_PASSWORD)


async def test_a_still_pending_account_rejects_a_reset_token():
    user = make_user(status="pending")
    use_case, users, tokens, _ = _build(user=user)
    token = await tokens.issue(user.id, ttl_seconds=3600)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_a_disabled_account_rejects_a_reset_token():
    user = make_user(status="disabled")
    use_case, users, tokens, _ = _build(user=user)
    token = await tokens.issue(user.id, ttl_seconds=3600)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_a_short_password_is_rejected_without_spending_the_token():
    user = make_user(status="active")
    use_case, _, tokens, _ = _build(user=user)
    token = await tokens.issue(user.id, ttl_seconds=3600)

    with pytest.raises(ValueError, match="at least"):
        await use_case.execute(token=token, password="short")

    assert await tokens.redeem(token) == user.id
