"""Tests for UpsertChannelAppUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.upsert_channel_app import UpsertChannelAppUseCase
from api_gateway.tests.support.fakes import FakeChannelAppRepo, FakeSecretGenerator

pytestmark = pytest.mark.anyio


def _build_use_case(channel_app=None, secret_generator=None):
    repo = FakeChannelAppRepo(channel_app)
    secret_generator = secret_generator or FakeSecretGenerator()
    use_case = UpsertChannelAppUseCase(channel_app_repo=repo, secret_generator=secret_generator)
    return use_case, repo, secret_generator


async def test_meta_without_verify_token_gets_one_generated():
    use_case, repo, secret_generator = _build_use_case()

    channel_app = await use_case.execute(
        provider="meta", credentials={"app_secret": "app-secret"}, config={}
    )

    assert channel_app.credentials["webhook_verify_token"] == secret_generator.value
    assert channel_app.credentials["app_secret"] == "app-secret"
    assert secret_generator.calls == 1


async def test_meta_preserves_explicit_verify_token():
    use_case, repo, secret_generator = _build_use_case()

    channel_app = await use_case.execute(
        provider="meta",
        credentials={"app_secret": "app-secret", "webhook_verify_token": "caller-supplied"},
        config={},
    )

    assert channel_app.credentials["webhook_verify_token"] == "caller-supplied"
    assert secret_generator.calls == 0


async def test_meta_update_preserves_previously_generated_token():
    existing = (await _build_use_case()[0].execute(provider="meta", credentials={}, config={}))
    secret_generator = FakeSecretGenerator(value="should-not-be-used")
    use_case, repo, _ = _build_use_case(channel_app=existing, secret_generator=secret_generator)

    channel_app = await use_case.execute(
        provider="meta", credentials={"app_secret": "rotated-secret"}, config={}
    )

    assert channel_app.credentials["webhook_verify_token"] == existing.credentials["webhook_verify_token"]
    assert channel_app.credentials["app_secret"] == "rotated-secret"
    assert secret_generator.calls == 0


async def test_provider_without_auto_secret_field_passes_through_untouched():
    use_case, repo, secret_generator = _build_use_case()

    channel_app = await use_case.execute(
        provider="twitter", credentials={"consumer_secret": "cs"}, config={}
    )

    assert channel_app.credentials == {"consumer_secret": "cs"}
    assert secret_generator.calls == 0


async def test_chatwoot_keeps_the_bot_the_gateway_created_when_an_admin_saves_again():
    use_case, repo, secret_generator = _build_use_case()
    await use_case.execute(provider="chatwoot", credentials={"api_access_token": "OLD"}, config={"account_id": 7})
    # What ChatwootClient.ensure_bot stores after creating the Agent Bot.
    await repo.upsert(
        provider="chatwoot",
        credentials={**repo.channel_app.credentials, "bot_access_token": "BOT"},
        config={**repo.channel_app.config, "bot_id": 42},
    )

    channel_app = await use_case.execute(provider="chatwoot", credentials={"api_access_token": "NEW"}, config={"account_id": 7})

    assert channel_app.credentials == {
        "api_access_token": "NEW",
        "webhook_token": secret_generator.value,
        "bot_access_token": "BOT",
    }
    assert channel_app.config == {"account_id": 7, "bot_id": 42}
    assert secret_generator.calls == 1


async def test_providers_without_managed_fields_are_stored_as_sent():
    use_case, repo, _ = _build_use_case()

    channel_app = await use_case.execute(provider="twilio", credentials={"auth_token": "T"}, config={"x": 1})

    assert (channel_app.credentials, channel_app.config) == ({"auth_token": "T"}, {"x": 1})
