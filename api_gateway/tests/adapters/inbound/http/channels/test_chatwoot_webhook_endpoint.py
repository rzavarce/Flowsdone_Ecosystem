"""End-to-end (ASGI, no real DB) tests for the Chatwoot Agent Bot webhook."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.adapters.inbound.http.channels.chatwoot import router
from app.domain.models.channel_app import ChannelApp
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeChannelAppRepo, FakeSwitchboard

pytestmark = pytest.mark.anyio

APP = ChannelApp(
    id=uuid4(),
    provider="chatwoot",
    credentials={"api_access_token": "ADMIN", "webhook_token": "WT"},
    config={"account_id": 7},
    created_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
    updated_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
)


def _event(**over):
    event = {
        "event": "message_created",
        "id": 5001,
        "content": "Hola, ¿tenéis cita mañana?",
        "message_type": "incoming",
        "private": False,
        "sender": {"id": 300, "name": "Ana López", "phone_number": None, "type": "contact"},
        "inbox": {"id": 15, "name": "Clínica Vital (Instagram)"},
        "conversation": {"id": 981, "inbox_id": 15, "channel": "Channel::Instagram", "status": "pending"},
        "account": {"id": 7, "name": "Flowsdone"},
    }
    event.update(over)
    return event


async def _post(event, token="WT", app=APP):
    switchboard = FakeSwitchboard()
    async with client_for_router(router, channel_app_repo=FakeChannelAppRepo(app), switchboard=switchboard) as client:
        response = await client.post("/webhooks/chatwoot", params={"token": token} if token else None, json=event)
    return response, switchboard


async def test_a_contacts_message_is_routed_by_inbox_with_the_conversation_as_key():
    response, switchboard = await _post(_event())

    assert response.status_code == 200
    call = switchboard.calls[0]
    assert call["channel_type"] == "chatwoot"
    assert call["external_id"] == "15"
    assert call["external_conversation_key"] == "981"
    assert call["sender_id"] == "300"
    assert call["message_text"] == "Hola, ¿tenéis cita mañana?"
    assert call["sender_profile"].name == "Ana López"


@pytest.mark.parametrize(
    "over",
    [
        {"message_type": "outgoing"},  # the bot's own reply echoed back
        {"message_type": "activity"},
        {"private": True},
        {"event": "conversation_status_changed"},
        {"content": "   "},
        {"account": {"id": 8}},  # another Chatwoot account
    ],
)
async def test_events_that_are_not_a_contacts_message_are_acknowledged_and_ignored(over):
    response, switchboard = await _post(_event(**over))

    assert response.status_code == 200
    assert switchboard.calls == []


@pytest.mark.parametrize("token, app", [(None, APP), ("wrong", APP), ("WT", None)])
async def test_a_missing_or_wrong_token_is_rejected(token, app):
    response, switchboard = await _post(_event(), token=token, app=app)

    assert response.status_code == 401
    assert switchboard.calls == []
