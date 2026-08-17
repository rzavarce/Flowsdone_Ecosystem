"""Tests for CreateChannelConnectionUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.webhook_registration import WebhookRegistrationError
from app.application.use_cases.create_channel_connection import (
    CreateChannelConnectionUseCase,
)
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeSecretGenerator,
    FakeWebhookRegistrar,
)

pytestmark = pytest.mark.anyio


def _build_use_case(registrars=None, secret_generator=None):
    repo = FakeChannelConnectionRepo()
    secret_generator = secret_generator or FakeSecretGenerator()
    use_case = CreateChannelConnectionUseCase(
        channel_connection_repo=repo,
        secret_generator=secret_generator,
        webhook_registrars=registrars or {},
    )
    return use_case, repo, secret_generator


async def test_channel_without_registrar_is_created_untouched():
    use_case, repo, secret_generator = _build_use_case()

    connection = await use_case.execute(
        project_id=uuid4(),
        agent_id=uuid4(),
        channel_type="whatsapp_evolution",
        external_id="instance-1",
        display_name=None,
        credentials={"note": "no secret needed"},
        config={},
    )

    assert connection.credentials == {"note": "no secret needed"}
    assert secret_generator.calls == 0
    assert repo.created[0]["channel_type"] == "whatsapp_evolution"


async def test_registrar_channel_auto_generates_missing_secret():
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret")
    use_case, repo, secret_generator = _build_use_case({"telegram": registrar})

    connection = await use_case.execute(
        project_id=uuid4(),
        agent_id=uuid4(),
        channel_type="telegram",
        external_id="123:ABC",
        display_name=None,
        credentials={},
        config={},
    )

    assert connection.credentials["telegram_webhook_secret"] == secret_generator.value
    assert registrar.register_calls == [
        {"external_id": "123:ABC", "credentials": {"telegram_webhook_secret": secret_generator.value}}
    ]


async def test_registrar_channel_preserves_explicit_secret():
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret")
    use_case, repo, secret_generator = _build_use_case({"telegram": registrar})

    connection = await use_case.execute(
        project_id=uuid4(),
        agent_id=uuid4(),
        channel_type="telegram",
        external_id="123:ABC",
        display_name=None,
        credentials={"telegram_webhook_secret": "caller-supplied"},
        config={},
    )

    assert connection.credentials["telegram_webhook_secret"] == "caller-supplied"
    assert secret_generator.calls == 0


async def test_registrar_without_secret_field_never_generates_one():
    """Meta-style registrar: secret_field=None, needs page_access_token instead."""
    registrar = FakeWebhookRegistrar(secret_field=None)
    use_case, repo, secret_generator = _build_use_case({"facebook": registrar})

    connection = await use_case.execute(
        project_id=uuid4(),
        agent_id=uuid4(),
        channel_type="facebook",
        external_id="PAGE123",
        display_name=None,
        credentials={"page_access_token": "TOKEN1"},
        config={},
    )

    assert connection.credentials == {"page_access_token": "TOKEN1"}
    assert secret_generator.calls == 0
    assert registrar.register_calls[0]["credentials"] == {"page_access_token": "TOKEN1"}


async def test_failed_registration_deletes_the_new_connection_and_raises():
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret", fail=True)
    use_case, repo, secret_generator = _build_use_case({"telegram": registrar})

    with pytest.raises(WebhookRegistrationError):
        await use_case.execute(
            project_id=uuid4(),
            agent_id=uuid4(),
            channel_type="telegram",
            external_id="123:ABC",
            display_name=None,
            credentials={},
            config={},
        )

    assert repo.connection is None
    assert len(repo.deleted) == 1
