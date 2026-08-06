"""Tests for UpsertChannelAppUseCase."""

from __future__ import annotations

import pytest

from api_gateway.app.application.use_cases.upsert_channel_app import UpsertChannelAppUseCase
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
