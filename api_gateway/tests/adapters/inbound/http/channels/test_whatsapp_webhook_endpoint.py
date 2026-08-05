"""End-to-end (ASGI, no real DB) tests for the WhatsApp (Evolution API) inbound webhook."""

from __future__ import annotations

import pytest

from api_gateway.app.adapters.inbound.http.channels import whatsapp_evolution as module
from api_gateway.app.adapters.inbound.http.channels.whatsapp_evolution import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeRouteChannelMessageUseCase

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
    route_use_case = FakeRouteChannelMessageUseCase()

    async with client_for_router(router, route_channel_message_use_case=route_use_case) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            headers={"apikey": "shared-evolution-key"},
            json=_upsert_event(),
        )

    assert response.status_code == 200
    assert len(route_use_case.calls) == 1
    call = route_use_case.calls[0]
    assert call["external_id"] == "instance-1"
    assert call["external_conversation_key"] == "5511999999999@s.whatsapp.net"
    assert call["payload"]["message"] == "hola"


async def test_wrong_apikey_is_rejected():
    route_use_case = FakeRouteChannelMessageUseCase()

    async with client_for_router(router, route_channel_message_use_case=route_use_case) as client:
        response = await client.post(
            "/webhooks/whatsapp", headers={"apikey": "wrong"}, json=_upsert_event()
        )

    assert response.status_code == 401
    assert route_use_case.calls == []


async def test_non_upsert_event_is_ignored():
    route_use_case = FakeRouteChannelMessageUseCase()

    async with client_for_router(router, route_channel_message_use_case=route_use_case) as client:
        response = await client.post(
            "/webhooks/whatsapp",
            headers={"apikey": "shared-evolution-key"},
            json={"event": "connection.update", "instance": "instance-1"},
        )

    assert response.status_code == 200
    assert route_use_case.calls == []


async def test_own_outgoing_message_is_ignored():
    route_use_case = FakeRouteChannelMessageUseCase()
    event = _upsert_event()
    event["data"]["key"]["fromMe"] = True

    async with client_for_router(router, route_channel_message_use_case=route_use_case) as client:
        response = await client.post(
            "/webhooks/whatsapp", headers={"apikey": "shared-evolution-key"}, json=event
        )

    assert response.status_code == 200
    assert route_use_case.calls == []
