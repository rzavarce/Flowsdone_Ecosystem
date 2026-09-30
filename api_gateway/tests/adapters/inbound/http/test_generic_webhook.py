"""Tests for POST /webhooks/generic: internal only, behind the admin API key."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.webhooks import router
from app.core.config import settings
from api_gateway.tests.support.asgi import client_for_router

pytestmark = pytest.mark.anyio

BODY = {"workflow_id": "flow-1", "conversation_id": "conv-1", "payload": {"message": "hola"}}


class FakeIngest:
    def __init__(self):
        self.calls = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Api-Key": "wrong"}])
async def test_without_the_admin_api_key_nothing_is_ingested(headers):
    ingest = FakeIngest()
    async with client_for_router(router, ingest_message_use_case=ingest) as client:
        response = await client.post("/webhooks/generic", json=BODY, headers=headers)

    assert response.status_code == 401
    assert ingest.calls == []


async def test_with_the_admin_api_key_the_message_is_ingested():
    ingest = FakeIngest()
    async with client_for_router(router, ingest_message_use_case=ingest) as client:
        response = await client.post(
            "/webhooks/generic", json=BODY, headers={"X-Admin-Api-Key": settings.ADMIN_API_KEY}
        )

    assert response.status_code == 200 and response.json() == {"status": "accepted"}
    [call] = ingest.calls
    assert call["workflow_id"] == "flow-1" and call["payload"] == {"message": "hola"}
