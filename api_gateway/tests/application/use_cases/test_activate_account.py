"""Tests for ActivateAccountUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.activate_account import ActivateAccountUseCase, InvalidTokenError
from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeAuthSessionRepo,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_user,
)

pytestmark = pytest.mark.anyio

NEW_PASSWORD = "x" * MIN_PASSWORD_LENGTH


def _build(*, pending_user=None):
    # ActivateAccountUseCase never issues its own token (that's
    # ProvisionUserUseCase's job) - tests issue one directly against the
    # same store to play that role.
    users = FakeUserRepo()
    if pending_user is not None:
        users.add(pending_user)
    tokens = FakeAccountTokenStore()
    sessions = FakeAuthSessionRepo()
    use_case = ActivateAccountUseCase(
        tokens=tokens,
        user_repo=users,
        tenant_repo=FakeTenantRepo(),
        hasher=FakePasswordHasher(),
        sessions=sessions,
        session_ttl_seconds=3600,
    )
    return use_case, users, tokens, sessions


async def _issue_token(tokens, user, ttl_seconds=86400):
    return await tokens.issue(user.id, ttl_seconds=ttl_seconds)


async def test_activates_hashes_the_password_and_opens_a_session():
    user = make_user(status="pending")
    use_case, users, tokens, sessions = _build(pending_user=user)
    token = await _issue_token(tokens, user)

    session_token, result = await use_case.execute(token=token, password=NEW_PASSWORD)

    assert result.id == user.id
    assert users.users[user.id].status == "active"
    assert users.hashes[user.id] == f"fake${NEW_PASSWORD}"
    assert sessions.sessions[session_token] == user.id
    assert users.logins == [user.id]


async def test_the_token_can_only_be_used_once():
    user = make_user(status="pending")
    use_case, _, tokens, _ = _build(pending_user=user)
    token = await _issue_token(tokens, user)

    await use_case.execute(token=token, password=NEW_PASSWORD)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_unknown_or_expired_token_is_rejected():
    use_case, *_ = _build()
    with pytest.raises(InvalidTokenError):
        await use_case.execute(token="nope", password=NEW_PASSWORD)


async def test_an_already_active_account_rejects_its_old_activation_token():
    user = make_user(status="active")
    use_case, users, tokens, _ = _build(pending_user=user)
    token = await _issue_token(tokens, user)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_a_disabled_account_rejects_the_token_even_if_still_pending_in_spirit():
    user = make_user(status="disabled")
    use_case, users, tokens, _ = _build(pending_user=user)
    token = await _issue_token(tokens, user)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)


async def test_a_short_password_is_rejected_without_spending_the_token():
    user = make_user(status="pending")
    use_case, _, tokens, _ = _build(pending_user=user)
    token = await _issue_token(tokens, user)

    with pytest.raises(ValueError, match="at least"):
        await use_case.execute(token=token, password="short")

    # The token is still good - a client bug shouldn't burn a valid link.
    assert await tokens.redeem(token) == user.id


async def test_deleted_user_between_issue_and_redeem_is_rejected():
    use_case, users, tokens, _ = _build()
    ghost_id = uuid4()
    token = await tokens.issue(ghost_id, ttl_seconds=86400)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(token=token, password=NEW_PASSWORD)
