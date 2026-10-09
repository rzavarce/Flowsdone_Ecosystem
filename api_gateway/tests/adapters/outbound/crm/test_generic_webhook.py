"""Tests for GenericWebhookProvider (the public signed-webhook contract)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app.adapters.outbound.crm import generic_webhook as module
from app.adapters.outbound.crm.generic_webhook import GenericWebhookProvider, signature
from app.domain.models.crm import CrmEvent
from app.domain.ports.outbound import CrmDeliveryError
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse
from api_gateway.tests.support.fakes import make_crm_integration

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "PUBLIC_BASE_URL", "https://platform.example.com")


def _event(integration):
    return CrmEvent(
        id=uuid4(), type="message.inbound", integration_id=integration.id, handoff_id=uuid4(),
        conversation_id="p1:whatsapp_360dialog:34699000111",
        occurred_at=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc), data={"text": "hola"},
    )


def _provider(allowed=True):
    async def ensure_allowed(url):
        if not allowed:
            raise ValueError("not allowed")
    return GenericWebhookProvider(ensure_allowed=ensure_allowed)


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


async def test_posts_a_signed_event_that_the_receiver_can_verify(monkeypatch):
    integration = make_crm_integration()
    event = _event(integration)
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))

    await _provider().deliver(event, integration)

    call = fake_client.calls[0]
    headers, body = call.kwargs["headers"], call.kwargs["content"]
    assert call.url == "https://crm.example.com/hooks/flowsdone"
    assert headers["X-Flowsdone-Event"] == "message.inbound"
    assert headers["X-Flowsdone-Event-Id"] == str(event.id)
    assert headers["X-Flowsdone-Signature"] == signature("SIGN", headers["X-Flowsdone-Timestamp"], body)
    sent = json.loads(body)
    assert sent["conversation_id"] == event.conversation_id
    assert sent["data"] == {"text": "hola"}
    assert sent["reply_url"] == f"https://platform.example.com/integrations/crm/{integration.id}/messages"
    assert sent["close_url"] == f"https://platform.example.com/integrations/crm/{integration.id}/close"


@pytest.mark.parametrize("status", [500, 503, 429, 408])
async def test_server_errors_and_throttling_are_retryable(monkeypatch, status):
    _patch_client(monkeypatch, lambda call: FakeResponse(status))
    integration = make_crm_integration()

    with pytest.raises(CrmDeliveryError):
        await _provider().deliver(_event(integration), integration)


async def test_network_errors_are_retryable(monkeypatch):
    def _raise(_call):
        raise httpx.ConnectError("down")

    _patch_client(monkeypatch, _raise)
    integration = make_crm_integration()

    with pytest.raises(CrmDeliveryError):
        await _provider().deliver(_event(integration), integration)


async def test_a_rejection_is_permanent(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(400, text="bad payload"))
    integration = make_crm_integration()

    with pytest.raises(ValueError):
        await _provider().deliver(_event(integration), integration)


async def test_a_forbidden_destination_is_never_called(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200))
    integration = make_crm_integration()

    with pytest.raises(ValueError):
        await _provider(allowed=False).deliver(_event(integration), integration)

    assert fake_client.calls == []
