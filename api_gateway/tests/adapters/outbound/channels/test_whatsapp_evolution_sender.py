"""Tests for WhatsAppEvolutionSender."""

from __future__ import annotations

import pytest

from api_gateway.app.adapters.outbound.channels import whatsapp_evolution_sender as module
from api_gateway.app.adapters.outbound.channels.whatsapp_evolution_sender import (
    WhatsAppEvolutionSender,
)
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "EVOLUTION_API_BASE_URL", "https://evo.example.com")
    monkeypatch.setattr(module.settings, "EVOLUTION_API_KEY", "shared-evolution-key")


async def test_sends_text_with_shared_evolution_api_key(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await WhatsAppEvolutionSender().send(
        external_id="instance-1", recipient_id="5511999999999@s.whatsapp.net", text="hola", credentials={}
    )

    call = fake_client.calls[0]
    assert call.url == "https://evo.example.com/message/sendText/instance-1"
    assert call.kwargs["headers"] == {"apikey": "shared-evolution-key"}
    assert call.kwargs["json"] == {"number": "5511999999999@s.whatsapp.net", "text": "hola"}


async def test_does_not_call_evolution_when_shared_key_is_unset(monkeypatch):
    monkeypatch.setattr(module.settings, "EVOLUTION_API_KEY", None)
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await WhatsAppEvolutionSender().send(
        external_id="instance-1", recipient_id="5511999999999", text="hola", credentials={}
    )

    assert fake_client.calls == []
