"""Public CRM API (/integrations/crm): API key auth and error mapping."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.crm import router
from app.application.use_cases.crm_handoff import HandoffNotOpenError, OutsideMessagingWindowError
from app.domain.models.messaging_window import MessagingDecision
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeCrmIntegrationRepository, make_crm_integration

pytestmark = pytest.mark.anyio


class Recorder:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error


async def _post(path_suffix, json, *, key="KEY", integration=None, reply=None, close=None):
    integration = integration or make_crm_integration()
    reply, close = reply or Recorder(), close or Recorder()
    async with client_for_router(
        router,
        crm_integration_repo=FakeCrmIntegrationRepository(integration),
        reply_from_crm_use_case=reply,
        close_handoff_use_case=close,
    ) as client:
        headers = {"X-Api-Key": key} if key else {}
        response = await client.post(f"/integrations/crm/{integration.id}/{path_suffix}", json=json, headers=headers)
    return response, reply, close, integration


async def test_the_agents_reply_is_accepted():
    response, reply, _, integration = await _post("messages", {"conversation_id": "c1", "text": "Hola"})

    assert response.status_code == 202
    assert reply.calls == [{"integration_id": integration.id, "conversation_id": "c1", "text": "Hola"}]


@pytest.mark.parametrize("key", [None, "wrong"])
async def test_a_missing_or_wrong_api_key_is_401(key):
    response, reply, _, _ = await _post("messages", {"conversation_id": "c1", "text": "Hola"}, key=key)

    assert response.status_code == 401 and reply.calls == []


async def test_an_inactive_integration_is_403():
    response, _, _, _ = await _post(
        "messages", {"conversation_id": "c1", "text": "x"}, integration=make_crm_integration(status="inactive")
    )

    assert response.status_code == 403


async def test_a_conversation_not_handed_over_is_409():
    response, _, _, _ = await _post("messages", {"conversation_id": "c1", "text": "x"}, reply=Recorder(HandoffNotOpenError("c1")))

    assert response.status_code == 409


async def test_a_closed_messaging_window_is_422_with_what_is_allowed():
    error = OutsideMessagingWindowError(MessagingDecision(mode="template_required"))
    response, _, _, _ = await _post("messages", {"conversation_id": "c1", "text": "x"}, reply=Recorder(error))

    assert response.status_code == 422
    assert response.json()["detail"] == {"error": "messaging_window_closed", "allowed": "template_required"}


async def test_closing_gives_the_conversation_back():
    response, _, close, integration = await _post("close", {"conversation_id": "c1"})

    assert response.status_code == 200 and response.json() == {"status": "closed"}
    assert close.calls == [{"integration_id": integration.id, "conversation_id": "c1"}]

    not_open, _, _, _ = await _post("close", {"conversation_id": "c1"}, close=Recorder(HandoffNotOpenError("c1")))
    assert not_open.status_code == 409
