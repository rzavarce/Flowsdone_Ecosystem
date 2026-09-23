"""Tests for RequestPasswordResetUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.request_password_reset import (
    RequestPasswordResetUseCase,
    TooManyAttemptsError,
)
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeEmailSender,
    FakeLoginThrottle,
    FakeUserRepo,
    make_user,
)

pytestmark = pytest.mark.anyio

PASSWORD = "correct-horse-battery"


def _build(*, max_email=3, max_ip=5, users=()):
    user_repo = FakeUserRepo()
    for user in users:
        user_repo.add(user, PASSWORD)
    tokens = FakeAccountTokenStore()
    mailer = FakeEmailSender()
    throttle = FakeLoginThrottle()
    use_case = RequestPasswordResetUseCase(
        user_repo=user_repo,
        tokens=tokens,
        mailer=mailer,
        throttle=throttle,
        ttl_seconds=3600,
        reset_base_url="https://app.flowsdone.com",
        window_seconds=900,
        max_requests_per_email=max_email,
        max_requests_per_ip=max_ip,
    )
    return use_case, user_repo, tokens, mailer, throttle


async def test_active_account_gets_a_reset_email_with_a_working_token():
    user = make_user(status="active", email="carla@cliente.com")
    use_case, _, tokens, mailer, _ = _build(users=[user])

    await use_case.execute(email=user.email)

    assert len(mailer.sent) == 1
    sent = mailer.sent[0]
    assert sent["to"] == "carla@cliente.com"
    assert sent["template"] == "password_reset"
    token = sent["context"]["link"].removeprefix("https://app.flowsdone.com/restablecer-password/")
    assert await tokens.redeem(token) == user.id


async def test_unknown_email_sends_nothing_but_still_succeeds():
    use_case, _, _, mailer, _ = _build()

    await use_case.execute(email="ghost@x.com")  # must not raise

    assert mailer.sent == []


async def test_pending_or_disabled_accounts_get_no_email():
    pending = make_user(status="pending", email="p@x.com")
    disabled = make_user(status="disabled", email="d@x.com")
    use_case, _, _, mailer, _ = _build(users=[pending, disabled])

    await use_case.execute(email=pending.email)
    await use_case.execute(email=disabled.email)

    assert mailer.sent == []


async def test_email_is_case_and_whitespace_insensitive():
    user = make_user(status="active", email="carla@cliente.com")
    use_case, _, _, mailer, _ = _build(users=[user])

    await use_case.execute(email="  CARLA@Cliente.COM ")

    assert mailer.sent[0]["to"] == "carla@cliente.com"


async def test_requests_are_throttled_per_email_regardless_of_whether_the_account_exists():
    use_case, _, _, _, throttle = _build(max_email=2)

    await use_case.execute(email="ghost@x.com")
    await use_case.execute(email="ghost@x.com")

    with pytest.raises(TooManyAttemptsError):
        await use_case.execute(email="ghost@x.com")


async def test_requests_are_throttled_per_ip_across_different_emails():
    use_case, _, _, _, throttle = _build(max_ip=2)

    await use_case.execute(email="a@x.com", client_ip="9.9.9.9")
    await use_case.execute(email="b@x.com", client_ip="9.9.9.9")

    with pytest.raises(TooManyAttemptsError):
        await use_case.execute(email="c@x.com", client_ip="9.9.9.9")
