"""End-to-end (ASGI, no real DB) tests for the X (Twitter) DM webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from app.adapters.inbound.http.channels.twitter import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeChannelAppRepo, FakeSwitchboard

pytestmark = pytest.mark.anyio

SECRET = "x-consumer-secret"


def _sign(message: bytes) -> str:
    return "sha256=" + base64.b64encode(hmac.new(SECRET.encode(), message, hashlib.sha256).digest()).decode()


def _repo():
    return FakeChannelAppRepo(SimpleNamespace(credentials={"consumer_secret": SECRET}))


def _dm(text="hola", sender="user-9"):
    return {"message_create": {"sender_id": sender, "message_data": {"text": text}}}


async def test_crc_challenge_answers_with_the_signed_token():
    async with client_for_router(router, channel_app_repo=_repo()) as client:
        response = await client.get("/webhooks/twitter", params={"crc_token": "abc"})

    assert response.status_code == 200
    assert response.json()["response_token"] == _sign(b"abc")


async def test_crc_challenge_without_token_is_a_bad_request():
    async with client_for_router(router, channel_app_repo=_repo()) as client:
        response = await client.get("/webhooks/twitter")

    assert response.status_code == 400


async def test_signed_direct_messages_are_routed():
    switchboard = FakeSwitchboard()
    body = json.dumps(
        {"for_user_id": "ACC1", "direct_message_events": [_dm("hola"), {"type": "other"}, _dm("", "user-8")]}
    ).encode()

    async with client_for_router(router, channel_app_repo=_repo(), switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/twitter", content=body,
            headers={"X-Twitter-Webhooks-Signature": _sign(body), "content-type": "application/json"},
        )

    assert response.status_code == 200
    [call] = switchboard.calls
    assert (call["external_id"], call["external_conversation_key"], call["message_text"]) == ("ACC1", "user-9", "hola")


async def test_an_invalid_signature_is_rejected_and_nothing_is_routed():
    switchboard = FakeSwitchboard()
    body = json.dumps({"for_user_id": "ACC1", "direct_message_events": [_dm()]}).encode()

    async with client_for_router(router, channel_app_repo=_repo(), switchboard=switchboard) as client:
        response = await client.post(
            "/webhooks/twitter", content=body,
            headers={"X-Twitter-Webhooks-Signature": "sha256=forged", "content-type": "application/json"},
        )

    assert response.status_code == 401 and switchboard.calls == []
