"""End-to-end (ASGI, no real DB) tests for the WhatsApp (Evolution API) inbound webhook."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.channels import whatsapp_evolution as module
from app.adapters.inbound.http.channels.whatsapp_evolution import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeSwitchboard

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_evolution_key(monkeypatch):
    monkeypatch.setattr(module.settings, "EVOLUTION_API_KEY", "shared-evolution-key")


def _upsert_event(**overrides):
    event = {
        "event": "messages.upsert",
        "instance": "instance-1",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "hola"},
        },
    }
    event.update(overrides)
    return event


async def test_valid_apikey_routes_the_message():
    switchboard = FakeSwitchboard()

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            headers={"apikey": "shared-evolution-key"},
            json=_upsert_event(),
        )

    assert response.status_code == 200
    assert len(switchboard.calls) == 1
    call = switchboard.calls[0]
    assert call["external_id"] == "instance-1"
    assert call["external_conversation_key"] == "5511999999999@s.whatsapp.net"
    assert call["message_text"] == "hola"


async def test_valid_apikey_in_body_routes_the_message():
    """Some Evolution API configurations send apikey as a top-level
    body field instead of (or in addition to) the "apikey" header -
    seen in production with Evolution 2.3.5's global webhook.
    """
    switchboard = FakeSwitchboard()

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            json=_upsert_event(apikey="shared-evolution-key"),
        )

    assert response.status_code == 200
    assert len(switchboard.calls) == 1


async def test_evolution_instance_apikey_is_also_accepted(monkeypatch):
    """Evolution doesn't echo EVOLUTION_API_KEY back in real webhook
    calls - it sends the per-instance token it auto-generated when the
    instance was created, which is a different value. Confirmed against
    a real webhook capture in production.
    """
    monkeypatch.setattr(module.settings, "EVOLUTION_WEBHOOK_API_KEY", "per-instance-token")
    switchboard = FakeSwitchboard()

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            json=_upsert_event(apikey="per-instance-token"),
        )

    assert response.status_code == 200
    assert len(switchboard.calls) == 1


async def test_wrong_apikey_is_rejected():
    switchboard = FakeSwitchboard()

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp", headers={"apikey": "wrong"}, json=_upsert_event()
        )

    assert response.status_code == 401
    assert switchboard.calls == []


async def test_non_upsert_event_is_ignored():
    switchboard = FakeSwitchboard()

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            headers={"apikey": "shared-evolution-key"},
            json={"event": "connection.update", "instance": "instance-1"},
        )

    assert response.status_code == 200
    assert switchboard.calls == []


async def test_own_outgoing_message_is_ignored():
    switchboard = FakeSwitchboard()
    event = _upsert_event()
    event["data"]["key"]["fromMe"] = True

    async with client_for_router(router, switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/whatsapp", headers={"apikey": "shared-evolution-key"}, json=event
        )

    assert response.status_code == 200
    assert switchboard.calls == []
