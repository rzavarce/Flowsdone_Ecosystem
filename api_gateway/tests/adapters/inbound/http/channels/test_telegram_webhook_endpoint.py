"""End-to-end (ASGI, no real DB) tests for the Telegram inbound webhook."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.channels.telegram import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeChannelConnectionRepo,
    FakeSwitchboard,
    make_channel_resolution,
)

pytestmark = pytest.mark.anyio

BOT_TOKEN = "123:BOT-TOKEN"


async def test_valid_secret_routes_the_message():
    conn_repo = FakeChannelConnectionRepo(
        resolution=make_channel_resolution(channel_type="telegram", credentials={"telegram_webhook_secret": "S3CR3T"})
    )
    switchboard = FakeSwitchboard()

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        switchboard=switchboard,
    ) as client:
        response = await client.post(
            f"/webhooks/telegram/{BOT_TOKEN}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "S3CR3T"},
            json={
                "message": {
                    "text": "hola",
                    "chat": {"id": 42},
                    "from": {"id": 7},
                }
            },
        )

    assert response.status_code == 200
    assert len(switchboard.calls) == 1
    call = switchboard.calls[0]
    assert call["external_id"] == BOT_TOKEN
    assert call["external_conversation_key"] == "42"
    assert call["message_text"] == "hola"


async def test_wrong_secret_is_rejected_and_does_not_route():
    conn_repo = FakeChannelConnectionRepo(
        resolution=make_channel_resolution(channel_type="telegram", credentials={"telegram_webhook_secret": "S3CR3T"})
    )
    switchboard = FakeSwitchboard()

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        switchboard=switchboard,
    ) as client:
        response = await client.post(
            f"/webhooks/telegram/{BOT_TOKEN}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json={"message": {"text": "hola", "chat": {"id": 42}, "from": {"id": 7}}},
        )

    assert response.status_code == 401
    assert switchboard.calls == []


async def test_unknown_bot_token_is_rejected():
    conn_repo = FakeChannelConnectionRepo(resolution=None)
    switchboard = FakeSwitchboard()

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        switchboard=switchboard,
    ) as client:
        response = await client.post(
            f"/webhooks/telegram/{BOT_TOKEN}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "whatever"},
            json={"message": {"text": "hola", "chat": {"id": 42}, "from": {"id": 7}}},
        )

    assert response.status_code == 401
    assert switchboard.calls == []


async def test_non_message_update_is_acknowledged_without_routing():
    conn_repo = FakeChannelConnectionRepo(
        resolution=make_channel_resolution(channel_type="telegram", credentials={"telegram_webhook_secret": "S3CR3T"})
    )
    switchboard = FakeSwitchboard()

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        switchboard=switchboard,
    ) as client:
        # An edited_message update, or anything without a plain "message", should
        # still be acknowledged (200) so Telegram doesn't retry, but not routed.
        response = await client.post(
            f"/webhooks/telegram/{BOT_TOKEN}",
            headers={"X-Telegram-Bot-Api-Secret-Token": "S3CR3T"},
            json={"edited_message": {"text": "editado"}},
        )

    assert response.status_code == 200
    assert switchboard.calls == []
