"""Tests for UpdateChannelConnectionUseCase."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.webhook_registration import WebhookRegistrationError
from app.application.use_cases.update_channel_connection import (
    UpdateChannelConnectionUseCase,
)
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeSecretGenerator,
    FakeWebhookRegistrar,
    make_channel_connection,
)

pytestmark = pytest.mark.anyio


def _build_use_case(connection, registrars=None, secret_generator=None):
    repo = FakeChannelConnectionRepo(connection=connection)
    secret_generator = secret_generator or FakeSecretGenerator()
    use_case = UpdateChannelConnectionUseCase(
        channel_connection_repo=repo,
        secret_generator=secret_generator,
        webhook_registrars=registrars or {},
    )
    return use_case, repo, secret_generator


async def test_unknown_connection_returns_none():
    use_case, repo, _ = _build_use_case(connection=None)

    result = await use_case.execute(uuid4(), display_name="new name")

    assert result is None


async def test_update_without_touching_credentials_never_reregisters():
    connection = make_channel_connection(
        channel_type="telegram", credentials={"telegram_webhook_secret": "OLD"}
    )
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret")
    use_case, repo, _ = _build_use_case(connection, {"telegram": registrar})

    result = await use_case.execute(connection.id, display_name="new name")

    assert result.credentials["telegram_webhook_secret"] == "OLD"
    assert registrar.register_calls == []


async def test_credentials_update_without_secret_preserves_previous_one():
    connection = make_channel_connection(
        channel_type="telegram", credentials={"telegram_webhook_secret": "OLD"}
    )
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret")
    use_case, repo, secret_generator = _build_use_case(connection, {"telegram": registrar})

    result = await use_case.execute(connection.id, credentials={"note": "unrelated change"})

    assert result.credentials["telegram_webhook_secret"] == "OLD"
    assert secret_generator.calls == 0
    assert registrar.register_calls == [
        {"external_id": connection.external_id, "credentials": {"note": "unrelated change", "telegram_webhook_secret": "OLD"}}
    ]


async def test_credentials_update_with_explicit_new_secret_reregisters_with_it():
    connection = make_channel_connection(
        channel_type="telegram", credentials={"telegram_webhook_secret": "OLD"}
    )
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret")
    use_case, repo, _ = _build_use_case(connection, {"telegram": registrar})

    result = await use_case.execute(
        connection.id, credentials={"telegram_webhook_secret": "NEW"}
    )

    assert result.credentials["telegram_webhook_secret"] == "NEW"
    assert registrar.register_calls[0]["credentials"]["telegram_webhook_secret"] == "NEW"


async def test_failed_reregistration_restores_previous_credentials_and_raises():
    connection = make_channel_connection(
        channel_type="telegram", credentials={"telegram_webhook_secret": "OLD"}
    )
    registrar = FakeWebhookRegistrar(secret_field="telegram_webhook_secret", fail=True)
    use_case, repo, _ = _build_use_case(connection, {"telegram": registrar})

    with pytest.raises(WebhookRegistrationError):
        await use_case.execute(connection.id, credentials={"telegram_webhook_secret": "BAD"})

    assert repo.connection.credentials["telegram_webhook_secret"] == "OLD"


async def test_channel_without_registrar_updates_freely():
    connection = make_channel_connection(channel_type="whatsapp_evolution", credentials={"a": 1})
    use_case, repo, _ = _build_use_case(connection, {"telegram": FakeWebhookRegistrar()})

    result = await use_case.execute(connection.id, credentials={"a": 2})

    assert result.credentials == {"a": 2}


async def test_config_update_merges_onto_existing_config_instead_of_replacing_it():
    connection = make_channel_connection(
        channel_type="voice",
        config={"provider": "twilio", "voice": "Polly.Mia-Neural", "tts_provider": "Amazon"},
    )
    use_case, repo, _ = _build_use_case(connection)

    result = await use_case.execute(connection.id, config={"welcome_greeting": "Hola!"})

    assert result.config == {
        "provider": "twilio",
        "voice": "Polly.Mia-Neural",
        "tts_provider": "Amazon",
        "welcome_greeting": "Hola!",
    }


async def test_config_update_overrides_a_key_already_present():
    connection = make_channel_connection(
        channel_type="voice", config={"provider": "twilio", "voice": "Polly.Andres-Neural"}
    )
    use_case, repo, _ = _build_use_case(connection)

    result = await use_case.execute(connection.id, config={"voice": "Polly.Mia-Neural"})

    assert result.config == {"provider": "twilio", "voice": "Polly.Mia-Neural"}


async def test_update_without_touching_config_leaves_it_unchanged():
    connection = make_channel_connection(
        channel_type="voice", config={"provider": "twilio", "voice": "Polly.Mia-Neural"}
    )
    use_case, repo, _ = _build_use_case(connection)

    result = await use_case.execute(connection.id, display_name="new name")

    assert result.config == {"provider": "twilio", "voice": "Polly.Mia-Neural"}
