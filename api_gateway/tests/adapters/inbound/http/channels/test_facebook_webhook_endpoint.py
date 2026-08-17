"""End-to-end (ASGI, no real DB) tests for the Facebook Messenger inbound webhook."""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from app.adapters.inbound.http.channels.facebook import router
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeChannelAppRepo, FakeSwitchboard

pytestmark = pytest.mark.anyio

APP_SECRET = "meta-app-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def test_get_verification_echoes_challenge_on_matching_token():
    channel_app_repo = FakeChannelAppRepo(
        SimpleNamespace(credentials={"webhook_verify_token": "verify-me"})
    )

    async with client_for_router(router, channel_app_repo=channel_app_repo) as client:
        response = await client.get(
            "/webhooks/facebook",
            params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "123"},
        )

    assert response.status_code == 200
    assert response.text == "123"


async def test_get_verification_rejects_wrong_token():
    channel_app_repo = FakeChannelAppRepo(
        SimpleNamespace(credentials={"webhook_verify_token": "verify-me"})
    )

    async with client_for_router(router, channel_app_repo=channel_app_repo) as client:
        response = await client.get(
            "/webhooks/facebook",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"},
        )

    assert response.status_code == 403


async def test_post_with_valid_signature_routes_each_message():
    channel_app_repo = FakeChannelAppRepo(SimpleNamespace(credentials={"app_secret": APP_SECRET}))
    switchboard = FakeSwitchboard()
    body = json.dumps(
        {
            "entry": [
                {
                    "id": "PAGE123",
                    "messaging": [
                        {"sender": {"id": "psid-1"}, "message": {"text": "hola"}},
                    ],
                }
            ]
        }
    ).encode()

    async with client_for_router(
        router, channel_app_repo=channel_app_repo, switchboard=switchboard
    ) as client:
        response = await client.post(
            "/webhooks/facebook",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "content-type": "application/json"},
        )

    assert response.status_code == 200
    assert len(switchboard.calls) == 1
    assert switchboard.calls[0]["external_id"] == "PAGE123"
    assert switchboard.calls[0]["external_conversation_key"] == "psid-1"


async def test_post_with_invalid_signature_is_rejected_and_does_not_route():
    channel_app_repo = FakeChannelAppRepo(SimpleNamespace(credentials={"app_secret": APP_SECRET}))
    switchboard = FakeSwitchboard()
    body = json.dumps({"entry": []}).encode()

    async with client_for_router(
        router, channel_app_repo=channel_app_repo, switchboard=switchboard
    ) as client:
        response = await client.post(
            "/webhooks/facebook",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=deadbeef", "content-type": "application/json"},
        )

    assert response.status_code == 401
    assert switchboard.calls == []


async def test_not_routable_message_still_acknowledged_200():
    channel_app_repo = FakeChannelAppRepo(SimpleNamespace(credentials={"app_secret": APP_SECRET}))
    switchboard = FakeSwitchboard(not_routable=True)
    body = json.dumps(
        {"entry": [{"id": "UNKNOWN_PAGE", "messaging": [{"sender": {"id": "psid-1"}, "message": {"text": "hi"}}]}]}
    ).encode()

    async with client_for_router(
        router, channel_app_repo=channel_app_repo, switchboard=switchboard
    ) as client:
        response = await client.post(
            "/webhooks/facebook",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "content-type": "application/json"},
        )

    # Meta must get 200 even when routing fails, or it retries forever.
    assert response.status_code == 200
