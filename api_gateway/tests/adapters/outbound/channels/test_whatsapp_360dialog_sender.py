"""Tests for WhatsApp360DialogSender."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.outbound.channels import d360_api
from app.adapters.outbound.channels import whatsapp_360dialog_sender as module
from app.adapters.outbound.channels.whatsapp_360dialog_sender import WhatsApp360DialogSender
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(d360_api.settings, "D360_API_BASE_URL", "https://waba-v2.360dialog.io")
    monkeypatch.setattr(d360_api.settings, "D360_SANDBOX_API_BASE_URL", "https://waba-sandbox.360dialog.io")


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


async def _send(credentials):
    await WhatsApp360DialogSender().send(
        external_id="34600111222", recipient_id="34699000111", text="hola", credentials=credentials
    )


async def test_sends_a_cloud_api_text_message_with_the_numbers_api_key(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"messages": [{"id": "wamid.1"}]}))

    await _send({"api_key": "KEY"})

    call = fake_client.calls[0]
    assert call.url == "https://waba-v2.360dialog.io/messages"
    assert call.kwargs["headers"] == {"D360-API-KEY": "KEY"}
    assert call.kwargs["json"] == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "34699000111",
        "type": "text",
        "text": {"body": "hola"},
    }


async def test_a_sandbox_connection_uses_the_sandbox_host(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    await _send({"api_key": "KEY", "sandbox": True})

    assert fake_client.calls[0].url == "https://waba-sandbox.360dialog.io/v1/messages"


async def test_without_api_key_nothing_is_sent(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    await _send({})

    assert fake_client.calls == []


@pytest.mark.parametrize("failure", ["status", "network"])
async def test_a_failed_delivery_is_logged_not_raised(monkeypatch, caplog, failure):
    def _respond(_call):
        if failure == "network":
            raise httpx.ConnectError("down")
        return FakeResponse(400, text="outside the 24h window")

    _patch_client(monkeypatch, _respond)

    await _send({"api_key": "KEY"})

    assert any(r.levelname == "ERROR" for r in caplog.records)
