"""Tests for ProvisionUserUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.create_user import CreateUserUseCase
from app.application.use_cases.provision_user import ProvisionUserUseCase
from app.domain.ports.outbound import EmailSendError, UserAlreadyExistsError
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeEmailSender,
    FakePasswordHasher,
    FakeTenantRepo,
    FakeUserRepo,
    make_tenant,
)

pytestmark = pytest.mark.anyio


class _BrokenMailer(FakeEmailSender):
    """Always fails, to test that the user stays created regardless."""

    async def send_template(self, **kwargs):
        raise EmailSendError("resend is down")


def _build(*, tenants=(), mailer=None):
    users = FakeUserRepo()
    create_user = CreateUserUseCase(
        user_repo=users, tenant_repo=FakeTenantRepo(list(tenants)), hasher=FakePasswordHasher()
    )
    tokens = FakeAccountTokenStore()
    mailer = mailer or FakeEmailSender()
    use_case = ProvisionUserUseCase(
        create_user=create_user,
        user_repo=users,
        tokens=tokens,
        mailer=mailer,
        ttl_seconds=86400,
        activation_base_url="https://app.flowsdone.com/",
    )
    return use_case, users, tokens, mailer


async def test_creates_the_user_pending_with_an_unusable_random_password():
    tenant = make_tenant()
    use_case, users, _, _ = _build(tenants=[tenant])

    user = await use_case.execute(email="carla@cliente.com", name="Carla", role="client", tenant_ids=[tenant.id])

    assert user.status == "pending"
    # A real password was generated and hashed (not None, not empty, not guessable).
    assert users.hashes[user.id] and users.hashes[user.id] != "fake$"


async def test_sends_the_activation_email_with_a_link_built_from_the_base_url():
    tenant = make_tenant()
    use_case, users, tokens, mailer = _build(tenants=[tenant])

    user = await use_case.execute(email="carla@cliente.com", name="Carla", role="client", tenant_ids=[tenant.id])

    assert len(mailer.sent) == 1
    sent = mailer.sent[0]
    assert sent["to"] == "carla@cliente.com"
    assert sent["template"] == "account_activation"
    assert sent["context"]["name"] == "Carla"
    assert sent["context"]["ttl_hours"] == 24
    token = sent["context"]["link"].removeprefix("https://app.flowsdone.com/activar-cuenta/")
    assert await tokens.redeem(token) == user.id


async def test_email_failure_does_not_undo_the_user_creation():
    tenant = make_tenant()
    use_case, users, _, _ = _build(tenants=[tenant], mailer=_BrokenMailer())

    with pytest.raises(EmailSendError):
        await use_case.execute(email="carla@cliente.com", name="Carla", role="client", tenant_ids=[tenant.id])

    assert len(users.users) == 1  # still there, just never got its email


async def test_duplicate_email_still_raises_user_already_exists():
    use_case, users, _, _ = _build()
    await use_case.execute(email="a@x.com", name="A", role="admin", tenant_ids=[])

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(email="A@x.com", name="A2", role="admin", tenant_ids=[])


async def test_resend_activation_sends_again_while_pending():
    use_case, users, tokens, mailer = _build()
    user = await use_case.execute(email="a@x.com", name="A", role="admin", tenant_ids=[])

    sent = await use_case.resend_activation(user.id)

    assert sent is True
    assert len(mailer.sent) == 2  # the original + the resend


async def test_resend_activation_is_a_noop_once_active_or_unknown():
    use_case, users, _, mailer = _build()
    user = await use_case.execute(email="a@x.com", name="A", role="admin", tenant_ids=[])
    await users.update(user.id, status="active")

    assert await use_case.resend_activation(user.id) is False
    assert await use_case.resend_activation(uuid4()) is False
    assert len(mailer.sent) == 1  # only the original creation email
