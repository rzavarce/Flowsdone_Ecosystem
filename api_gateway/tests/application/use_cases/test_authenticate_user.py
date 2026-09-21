"""Tests for AuthenticateUserUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.authenticate_user import (
    AuthenticateUserUseCase,
    InvalidCredentialsError,
    TooManyAttemptsError,
)
from api_gateway.tests.support.fakes import (
    FakeAuthSessionRepo,
    FakeLoginThrottle,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
    make_user,
)

pytestmark = pytest.mark.anyio

PASSWORD = "correct-horse-battery"


def _setup(*, max_email=3, max_ip=5, users=(), tenants=()):
    user_repo = FakeUserRepo()
    for user in users:
        user_repo.add(user, PASSWORD)
    hasher = FakePasswordHasher()
    sessions, throttle = FakeAuthSessionRepo(), FakeLoginThrottle()
    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        tenant_repo=FakeTenantRepo(list(tenants)),
        hasher=hasher,
        sessions=sessions,
        throttle=throttle,
        session_ttl_seconds=3600,
        window_seconds=900,
        max_failures_per_email=max_email,
        max_failures_per_ip=max_ip,
    )
    return use_case, user_repo, hasher, sessions, throttle


async def test_valid_login_opens_a_session_and_returns_the_user():
    user = make_user()
    use_case, user_repo, _, sessions, _ = _setup(users=[user])

    token, result = await use_case.execute(email=user.email, password=PASSWORD)

    assert sessions.sessions[token] == user.id
    assert sessions.ttls[token] == 3600
    assert result.id == user.id and result.role == "client"
    assert user_repo.logins == [user.id]


async def test_email_is_case_and_whitespace_insensitive():
    user = make_user(email="carla@cliente.com")
    use_case, *_ = _setup(users=[user])

    _, result = await use_case.execute(email="  CARLA@Cliente.COM ", password=PASSWORD)

    assert result.email == "carla@cliente.com"


async def test_admin_gets_every_tenant():
    a, b = make_tenant(name="A", slug="a"), make_tenant(name="B", slug="b")
    admin = make_user(role="admin", email="ana@x.com")
    use_case, *_ = _setup(users=[admin], tenants=[a, b])

    _, result = await use_case.execute(email=admin.email, password=PASSWORD)

    assert {t.name for t in result.tenants} == {"A", "B"}


async def test_non_admin_only_gets_their_own_tenants():
    a, b = make_tenant(name="A", slug="a"), make_tenant(name="B", slug="b")
    manager = make_user(role="tenant_manager", email="m@x.com", tenant_ids=[a.id])
    use_case, *_ = _setup(users=[manager], tenants=[a, b])

    _, result = await use_case.execute(email=manager.email, password=PASSWORD)

    assert [t.name for t in result.tenants] == ["A"]


async def test_wrong_password_is_rejected_and_opens_no_session():
    user = make_user()
    use_case, user_repo, _, sessions, _ = _setup(users=[user])

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email=user.email, password="nope")

    assert sessions.sessions == {}
    assert user_repo.logins == []


async def test_unknown_email_is_rejected_the_same_way_and_still_hashes():
    use_case, _, hasher, _, _ = _setup()

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="ghost@x.com", password="whatever")

    # Se verificó contra un hash señuelo: mismo trabajo que con un email real.
    assert len(hasher.verify_calls) == 1


async def test_disabled_account_is_indistinguishable_from_wrong_credentials():
    user = make_user(status="disabled")
    use_case, _, _, sessions, _ = _setup(users=[user])

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email=user.email, password=PASSWORD)

    assert sessions.sessions == {}


async def test_failures_are_counted_per_email_and_per_ip_with_the_window():
    use_case, _, _, _, throttle = _setup()

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="ghost@x.com", password="x", client_ip="1.2.3.4")

    assert throttle.counts == {"email:ghost@x.com": 1, "ip:1.2.3.4": 1}
    assert set(throttle.windows.values()) == {900}


async def test_account_is_blocked_after_max_failures_even_with_the_right_password():
    user = make_user()
    use_case, _, _, sessions, _ = _setup(max_email=3, users=[user])

    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email=user.email, password="bad")

    with pytest.raises(TooManyAttemptsError):
        await use_case.execute(email=user.email, password=PASSWORD)
    assert sessions.sessions == {}


async def test_blocking_an_account_does_not_depend_on_the_client_ip():
    # Rotar la IP (p. ej. X-Forwarded-For falsificado) no evita el bloqueo por cuenta.
    user = make_user()
    use_case, *_ = _setup(max_email=2, users=[user])

    for ip in ("1.1.1.1", "2.2.2.2"):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email=user.email, password="bad", client_ip=ip)

    with pytest.raises(TooManyAttemptsError):
        await use_case.execute(email=user.email, password=PASSWORD, client_ip="3.3.3.3")


async def test_ip_is_blocked_after_max_failures_across_different_accounts():
    use_case, *_ = _setup(max_ip=2)

    for i in range(2):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email=f"u{i}@x.com", password="bad", client_ip="9.9.9.9")

    with pytest.raises(TooManyAttemptsError):
        await use_case.execute(email="another@x.com", password="bad", client_ip="9.9.9.9")


async def test_successful_login_resets_the_account_counter():
    user = make_user()
    use_case, _, _, _, throttle = _setup(max_email=3, users=[user])

    for _ in range(2):
        with pytest.raises(InvalidCredentialsError):
            await use_case.execute(email=user.email, password="bad")
    await use_case.execute(email=user.email, password=PASSWORD)

    assert await throttle.failures(f"email:{user.email}") == 0
