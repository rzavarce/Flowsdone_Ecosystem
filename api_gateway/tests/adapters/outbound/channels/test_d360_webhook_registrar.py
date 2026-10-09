"""Tests for D360WebhookRegistrar."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.outbound.channels import d360_api
from app.adapters.outbound.channels import d360_webhook_registrar as module
from app.adapters.outbound.channels.d360_webhook_registrar import (
    D360WebhookRegistrar,
    D360WebhookRegistrationError,
)
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio

CREDENTIALS = {"api_key": "KEY", "d360_webhook_secret": "S3CR3T"}


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(d360_api.settings, "D360_API_BASE_URL", "https://waba-v2.360dialog.io")
    monkeypatch.setattr(d360_api.settings, "D360_SANDBOX_API_BASE_URL", "https://waba-sandbox.360dialog.io")
    monkeypatch.setattr(d360_api.settings, "PUBLIC_BASE_URL", "https://platform.example.com")


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


def test_the_secret_is_generated_by_the_gateway():
    assert D360WebhookRegistrar().secret_field == "d360_webhook_secret"


async def test_register_sets_our_callback_url_and_the_secret_header(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"url": "ok"}))

    await D360WebhookRegistrar().register(external_id="34600111222", credentials=CREDENTIALS)

    call = fake_client.calls[0]
    assert call.url == "https://waba-v2.360dialog.io/v1/configs/webhook"
    assert call.kwargs["headers"] == {"D360-API-KEY": "KEY"}
    assert call.kwargs["json"] == {
        "url": "https://platform.example.com/webhooks/whatsapp-360dialog/34600111222",
        "headers": {"X-Flowsdone-Webhook-Secret": "S3CR3T"},
    }


async def test_register_on_a_sandbox_connection_uses_the_sandbox_host(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    await D360WebhookRegistrar().register(external_id="1", credentials=CREDENTIALS, config={"sandbox": True})

    assert fake_client.calls[0].url == "https://waba-sandbox.360dialog.io/v1/configs/webhook"


async def test_register_without_api_key_fails_before_calling_360dialog(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    with pytest.raises(D360WebhookRegistrationError):
        await D360WebhookRegistrar().register(external_id="1", credentials={"d360_webhook_secret": "s"})

    assert fake_client.calls == []


async def test_register_raises_when_360dialog_rejects_it(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(401, text="invalid api key"))

    with pytest.raises(D360WebhookRegistrationError):
        await D360WebhookRegistrar().register(external_id="1", credentials=CREDENTIALS)


async def test_register_raises_when_360dialog_is_unreachable(monkeypatch):
    def _raise(_call):
        raise httpx.ConnectError("no network")

    _patch_client(monkeypatch, _raise)

    with pytest.raises(D360WebhookRegistrationError):
        await D360WebhookRegistrar().register(external_id="1", credentials=CREDENTIALS)


async def test_deregister_makes_no_call(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    await D360WebhookRegistrar().deregister(external_id="1", credentials=CREDENTIALS)

    assert fake_client.calls == []
