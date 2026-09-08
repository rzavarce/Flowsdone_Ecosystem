"""End-to-end (ASGI, no real DB) tests for the voice human-transfer webhook."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.adapters.inbound.http.voice.handoff import router
from app.domain.models.channel_app import ChannelApp
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeChannelAppRepo, FakeVoiceProvider

pytestmark = pytest.mark.anyio


def _channel_app() -> ChannelApp:
    now = datetime.now(timezone.utc)
    return ChannelApp(
        id=uuid4(), provider="twilio", credentials={"auth_token": "tok"}, config={}, created_at=now, updated_at=now
    )


async def test_valid_handoff_dials_the_transfer_number_with_caller_id():
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router, channel_app_repo=app_repo, voice_provider=voice_provider
    ) as client:
        response = await client.post(
            "/webhooks/voice/handoff",
            data={
                "CallSid": "CA123",
                "HandoffData": json.dumps(
                    {
                        "reason": "human_transfer",
                        "transfer_number": "+34601491522",
                        "caller_id": "+16014944500",
                    }
                ),
            },
            headers={"X-Twilio-Signature": "sig"},
        )

    assert response.status_code == 200
    assert "<Dial>+34601491522</Dial>" in response.text
    assert voice_provider.built_handoff_calls == [
        {"phone_number": "+34601491522", "caller_id": "+16014944500"}
    ]


async def test_invalid_signature_is_rejected():
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    voice_provider = FakeVoiceProvider(signature_valid=False)

    async with client_for_router(
        router, channel_app_repo=app_repo, voice_provider=voice_provider
    ) as client:
        response = await client.post(
            "/webhooks/voice/handoff",
            data={"CallSid": "CA123", "HandoffData": json.dumps({"transfer_number": "+34601491522"})},
            headers={"X-Twilio-Signature": "wrong"},
        )

    assert response.status_code == 401
    assert voice_provider.built_handoff_for == []


async def test_malformed_handoff_data_is_rejected():
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router, channel_app_repo=app_repo, voice_provider=voice_provider
    ) as client:
        response = await client.post(
            "/webhooks/voice/handoff",
            data={"CallSid": "CA123", "HandoffData": "not-json"},
            headers={"X-Twilio-Signature": "sig"},
        )

    assert response.status_code == 400
    assert voice_provider.built_handoff_for == []


async def test_handoff_data_missing_transfer_number_is_rejected():
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router, channel_app_repo=app_repo, voice_provider=voice_provider
    ) as client:
        response = await client.post(
            "/webhooks/voice/handoff",
            data={"CallSid": "CA123", "HandoffData": json.dumps({"reason": "human_transfer"})},
            headers={"X-Twilio-Signature": "sig"},
        )

    assert response.status_code == 400
