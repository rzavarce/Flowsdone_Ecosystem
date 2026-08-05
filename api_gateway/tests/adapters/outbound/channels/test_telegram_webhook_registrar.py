"""Tests for TelegramWebhookRegistrar."""

from __future__ import annotations

import pytest

from api_gateway.app.adapters.outbound.channels import telegram_webhook_registrar as module
from api_gateway.app.adapters.outbound.channels.telegram_webhook_registrar import (
    TelegramWebhookRegistrar,
    TelegramWebhookRegistrationError,
)
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    monkeypatch.setattr(module.settings, "PUBLIC_BASE_URL", "https://platform.example.com")


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


async def test_register_calls_set_webhook_with_public_callback_url_and_secret(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"ok": True}))
    registrar = TelegramWebhookRegistrar()

    await registrar.register(external_id="123:BOT", credentials={"telegram_webhook_secret": "S3CR3T"})

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call.url == "https://api.telegram.org/bot123:BOT/setWebhook"
    assert call.kwargs["data"] == {
        "url": "https://platform.example.com/webhooks/telegram/123:BOT",
        "secret_token": "S3CR3T",
    }


async def test_register_raises_when_telegram_responds_not_ok(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"ok": False, "description": "bad token"}))
    registrar = TelegramWebhookRegistrar()

    with pytest.raises(TelegramWebhookRegistrationError):
        await registrar.register(external_id="bad", credentials={"telegram_webhook_secret": "s"})


async def test_register_raises_on_http_error_status(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(404, text="Not Found", headers={}))
    registrar = TelegramWebhookRegistrar()

    with pytest.raises(TelegramWebhookRegistrationError):
        await registrar.register(external_id="bad", credentials={"telegram_webhook_secret": "s"})


async def test_register_raises_when_network_unreachable(monkeypatch):
    import httpx

    def _raise(_call):
        raise httpx.ConnectError("no network")

    _patch_client(monkeypatch, _raise)
    registrar = TelegramWebhookRegistrar()

    with pytest.raises(TelegramWebhookRegistrationError):
        await registrar.register(external_id="bot", credentials={"telegram_webhook_secret": "s"})


async def test_deregister_calls_delete_webhook(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"ok": True}))
    registrar = TelegramWebhookRegistrar()

    await registrar.deregister(external_id="123:BOT", credentials={})

    assert fake_client.calls[0].url == "https://api.telegram.org/bot123:BOT/deleteWebhook"


def test_secret_field_is_telegram_webhook_secret():
    assert TelegramWebhookRegistrar().secret_field == "telegram_webhook_secret"
