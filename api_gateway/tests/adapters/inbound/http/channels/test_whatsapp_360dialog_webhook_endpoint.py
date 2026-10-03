"""End-to-end (ASGI, no real DB) tests for the 360dialog inbound webhook."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.channels.whatsapp_360dialog import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeSwitchboard,
    make_channel_resolution,
)

pytestmark = pytest.mark.anyio

NUMBER = "34600111222"
URL = f"/webhooks/whatsapp-360dialog/{NUMBER}"
SECRET_HEADER = {"X-Flowsdone-Webhook-Secret": "S3CR3T"}


def _repo():
    return FakeChannelConnectionRepo(
        resolution=make_channel_resolution(
            channel_type="whatsapp_360dialog", credentials={"api_key": "K", "d360_webhook_secret": "S3CR3T"}
        )
    )


def _body(*messages, contacts=None, statuses=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"}}
    if contacts is not None:
        value["contacts"] = contacts
    if messages:
        value["messages"] = list(messages)
    if statuses:
        value["statuses"] = statuses
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": value}]}]}


def _text(body, wa_id="34699000111"):
    return {"from": wa_id, "id": "wamid.1", "timestamp": "1700000000", "type": "text", "text": {"body": body}}


async def _post(json, headers=SECRET_HEADER, repo=None, switchboard=None):
    switchboard = switchboard or FakeSwitchboard()
    async with client_for_router(router, channel_connection_repo=repo or _repo(), switchboard=switchboard) as client:
        response = await client.post(URL, headers=headers, json=json)
    return response, switchboard


async def test_a_text_message_is_routed_with_the_senders_number_as_conversation_key():
    response, switchboard = await _post(
        _body(_text("hola"), contacts=[{"wa_id": "34699000111", "profile": {"name": " Ana "}}])
    )

    assert response.status_code == 200
    call = switchboard.calls[0]
    assert call["channel_type"] == "whatsapp_360dialog"
    assert call["external_id"] == NUMBER
    assert call["external_conversation_key"] == "34699000111"
    assert call["message_text"] == "hola"
    assert (call["sender_profile"].name, call["sender_profile"].phone) == ("Ana", "+34699000111")


@pytest.mark.parametrize(
    "message, expected",
    [
        ({"type": "button", "button": {"text": "Sí, quiero"}}, "Sí, quiero"),
        ({"type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "b1", "title": "Opción A"}}}, "Opción A"),
        ({"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": "l1", "title": "Mañana"}}}, "Mañana"),
    ],
)
async def test_button_and_list_replies_are_routed_as_text(message, expected):
    _, switchboard = await _post(_body({"from": "34699000111", "id": "wamid.2", **message}))

    assert switchboard.calls[0]["message_text"] == expected


async def test_media_messages_and_status_updates_are_acknowledged_but_not_routed():
    response, switchboard = await _post(
        _body(
            {"from": "34699000111", "id": "wamid.3", "type": "image", "image": {"id": "MEDIA"}},
            statuses=[{"id": "wamid.0", "status": "delivered", "recipient_id": "34699000111"}],
        )
    )

    assert response.status_code == 200
    assert switchboard.calls == []


async def test_the_sandbox_payload_without_metadata_is_routed_too():
    sandbox_body = {"entry": [{"changes": [{"field": "messages", "value": {
        "contacts": [{"profile": {"name": "Ana"}, "wa_id": "34699000111"}],
        "messages": [_text("START")],
    }}]}]}

    _, switchboard = await _post(sandbox_body)

    assert switchboard.calls[0]["message_text"] == "START"


@pytest.mark.parametrize("headers", [{}, {"X-Flowsdone-Webhook-Secret": "wrong"}])
async def test_a_missing_or_wrong_secret_is_rejected_and_not_routed(headers):
    response, switchboard = await _post(_body(_text("hola")), headers=headers)

    assert response.status_code == 401
    assert switchboard.calls == []


async def test_a_number_that_is_no_longer_connected_is_acknowledged_so_360dialog_stops_retrying():
    response, switchboard = await _post(_body(_text("hola")), repo=FakeChannelConnectionRepo(resolution=None))

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert switchboard.calls == []
