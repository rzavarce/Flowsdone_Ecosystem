"""Tests for CreateTenantUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.create_tenant import CreateTenantUseCase
from app.application.use_cases.create_user import CreateUserUseCase
from app.application.use_cases.provision_user import ProvisionUserUseCase
from app.domain.ports.outbound import UserAlreadyExistsError
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeEmailSender,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_user,
)

pytestmark = pytest.mark.anyio


def _build():
    tenants = FakeTenantRepo()
    users = FakeUserRepo()
    create_user = CreateUserUseCase(user_repo=users, tenant_repo=tenants, hasher=FakePasswordHasher())
    mailer = FakeEmailSender()
    provision_user = ProvisionUserUseCase(
        create_user=create_user,
        user_repo=users,
        tokens=FakeAccountTokenStore(),
        mailer=mailer,
        ttl_seconds=86400,
        activation_base_url="https://app.flowsdone.com",
    )
    use_case = CreateTenantUseCase(tenant_repo=tenants, user_repo=users, provision_user=provision_user)
    return use_case, tenants, users, mailer


async def test_creates_the_tenant_and_its_pending_client_user():
    use_case, tenants, users, mailer = _build()

    tenant = await use_case.execute(
        name="Clínica Vital", slug="clinica-vital", client_email="ana@clinica.com", client_name="Ana"
    )

    assert tenant.slug == "clinica-vital"
    [client] = [u for u in users.users.values() if u.email == "ana@clinica.com"]
    assert client.role == "client" and client.status == "pending" and client.tenant_ids == [tenant.id]
    assert len(mailer.sent) == 1 and mailer.sent[0]["to"] == "ana@clinica.com"


async def test_a_duplicate_client_email_is_rejected_before_the_tenant_is_created():
    use_case, tenants, users, _ = _build()
    users.add(make_user(email="ana@clinica.com"))

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(
            name="Clínica Vital", slug="clinica-vital", client_email="Ana@Clinica.com", client_name="Ana"
        )

    assert tenants.tenants == []  # never got created - not an orphan
