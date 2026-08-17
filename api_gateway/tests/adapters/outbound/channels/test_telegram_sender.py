"""Tests for TelegramSender."""

from __future__ import annotations

import pytest

from app.adapters.outbound.channels import telegram_sender as module
from app.adapters.outbound.channels.telegram_sender import TelegramSender
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "TELEGRAM_API_BASE_URL", "https://api.telegram.org")


async def test_sends_text_message_to_the_right_chat(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200, json_body={"ok": True}))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await TelegramSender().send(
        external_id="123:BOT", recipient_id="chat-1", text="hola", credentials={}
    )

    call = fake_client.calls[0]
    assert call.url == "https://api.telegram.org/bot123:BOT/sendMessage"
    assert call.kwargs["json"] == {"chat_id": "chat-1", "text": "hola"}


async def test_does_not_raise_when_telegram_rejects_the_send(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(400, text="bad request"))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    # Senders never raise on delivery failure - it's logged, not propagated.
    await TelegramSender().send(
        external_id="123:BOT", recipient_id="chat-1", text="hola", credentials={}
    )
