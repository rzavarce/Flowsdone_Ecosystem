"""Tests for CreateUserUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH, CreateUserUseCase
from app.domain.ports.outbound import UserAlreadyExistsError
from api_gateway.tests.support.fakes import FakePasswordHasher, FakeTenantRepo, FakeUserRepo, make_tenant

pytestmark = pytest.mark.anyio

GOOD_PASSWORD = "x" * MIN_PASSWORD_LENGTH


def _build(tenants=()):
    users = FakeUserRepo()
    return CreateUserUseCase(
        user_repo=users, tenant_repo=FakeTenantRepo(list(tenants)), hasher=FakePasswordHasher()
    ), users


async def test_creates_a_user_with_a_hashed_password_and_normalized_email():
    tenant = make_tenant()
    use_case, users = _build([tenant])

    user = await use_case.execute(
        email="  Carla@Cliente.COM ", name=" Carla ", role="client", password=GOOD_PASSWORD, tenant_ids=[tenant.id]
    )

    assert user.email == "carla@cliente.com" and user.name == "Carla"
    assert users.hashes[user.id] == f"fake${GOOD_PASSWORD}"
    assert user.tenant_ids == [tenant.id]


async def test_admin_needs_no_tenants_and_memberships_are_dropped():
    use_case, _ = _build([make_tenant()])

    user = await use_case.execute(
        email="ana@x.com", name="Ana", role="admin", password=GOOD_PASSWORD, tenant_ids=[uuid4()]
    )

    assert user.role == "admin" and user.tenant_ids == []


@pytest.mark.parametrize("role", ["tenant_manager", "botmaster", "client"])
async def test_non_admin_roles_require_at_least_one_tenant(role):
    use_case, _ = _build()
    with pytest.raises(ValueError, match="at least one tenant"):
        await use_case.execute(email="a@x.com", name="A", role=role, password=GOOD_PASSWORD, tenant_ids=[])


async def test_unknown_tenant_is_rejected():
    use_case, _ = _build([make_tenant()])
    with pytest.raises(ValueError, match="unknown tenant"):
        await use_case.execute(
            email="a@x.com", name="A", role="client", password=GOOD_PASSWORD, tenant_ids=[uuid4()]
        )


@pytest.mark.parametrize(
    "overrides, message",
    [
        (dict(email="not-an-email"), "invalid email"),
        (dict(name="   "), "name is required"),
        (dict(role="root"), "role must be one of"),
        (dict(password="short"), "at least"),
    ],
)
async def test_invalid_input_is_rejected(overrides, message):
    use_case, _ = _build()
    args = dict(email="a@x.com", name="A", role="admin", password=GOOD_PASSWORD, tenant_ids=[])
    args.update(overrides)
    with pytest.raises(ValueError, match=message):
        await use_case.execute(**args)


async def test_status_defaults_to_active_but_can_be_overridden():
    # Default keeps the CLI bootstrap (app/cli/create_user.py) working
    # unchanged; ProvisionUserUseCase is the one that passes "pending".
    use_case, users = _build()

    default_status = await use_case.execute(
        email="a@x.com", name="A", role="admin", password=GOOD_PASSWORD, tenant_ids=[]
    )
    pending = await use_case.execute(
        email="b@x.com", name="B", role="admin", password=GOOD_PASSWORD, tenant_ids=[], status="pending"
    )

    assert default_status.status == "active"
    assert pending.status == "pending"


async def test_duplicate_email_raises_user_already_exists():
    use_case, _ = _build()
    args = dict(email="a@x.com", name="A", role="admin", password=GOOD_PASSWORD, tenant_ids=[])
    await use_case.execute(**args)

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(**{**args, "email": "A@X.com"})
