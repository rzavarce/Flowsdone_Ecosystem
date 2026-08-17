"""End-to-end (ASGI, no real DB) tests for the voice incoming-call webhook."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.adapters.inbound.http.voice.webhook import router
from app.domain.models.channel_app import ChannelApp
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import (
    FakeCallSessionRepo,
    FakeChannelAppRepo,
    FakeChannelConnectionRepo,
    FakeVoiceProvider,
    make_channel_resolution,
)

pytestmark = pytest.mark.anyio

CALL_PARAMS = {"To": "+15559998888", "From": "+15550001111", "CallSid": "CA123"}


def _channel_app() -> ChannelApp:
    now = datetime.now(timezone.utc)
    return ChannelApp(
        id=uuid4(),
        provider="twilio",
        credentials={"auth_token": "tok"},
        config={},
        created_at=now,
        updated_at=now,
    )


async def test_valid_call_returns_twiml_and_saves_a_call_session():
    conn_repo = FakeChannelConnectionRepo(resolution=make_channel_resolution(channel_type="voice"))
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        response = await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    assert response.status_code == 200
    assert "ConversationRelay" in response.text
    assert "/voice/stream/CA123" in response.text
    assert call_session_repo.sessions["CA123"].to_number == "+15559998888"


async def test_valid_call_passes_the_connections_voice_config_through_to_the_provider():
    resolution = make_channel_resolution(
        channel_type="voice", config={"voice": "Google.es-US-Neural2-A", "language": "es-MX"}
    )
    conn_repo = FakeChannelConnectionRepo(resolution=resolution)
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    assert voice_provider.built_twiml_calls[0]["voice"] == "Google.es-US-Neural2-A"
    assert voice_provider.built_twiml_calls[0]["language"] == "es-MX"


async def test_valid_call_requests_an_action_url_when_human_transfer_is_configured():
    resolution = make_channel_resolution(
        channel_type="voice",
        config={"human_transfer_number": "+34601491522", "human_transfer_phrases": ["agente humano"]},
    )
    conn_repo = FakeChannelConnectionRepo(resolution=resolution)
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    action_url = voice_provider.built_twiml_calls[0]["action_url"]
    assert action_url is not None
    assert action_url.endswith("/webhooks/voice/handoff")
    assert call_session_repo.sessions["CA123"].config["human_transfer_number"] == "+34601491522"


async def test_valid_call_omits_action_url_when_no_human_transfer_configured():
    conn_repo = FakeChannelConnectionRepo(resolution=make_channel_resolution(channel_type="voice"))
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    assert voice_provider.built_twiml_calls[0]["action_url"] is None


async def test_invalid_signature_is_rejected_without_saving_a_session():
    conn_repo = FakeChannelConnectionRepo(resolution=make_channel_resolution(channel_type="voice"))
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=False)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        response = await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "wrong"}
        )

    assert response.status_code == 401
    assert call_session_repo.sessions == {}


async def test_missing_twilio_app_credentials_is_rejected():
    conn_repo = FakeChannelConnectionRepo(resolution=make_channel_resolution(channel_type="voice"))
    app_repo = FakeChannelAppRepo(channel_app=None)
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        response = await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    assert response.status_code == 401
    assert call_session_repo.sessions == {}


async def test_unknown_number_is_rejected():
    conn_repo = FakeChannelConnectionRepo(resolution=None)
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        response = await client.post(
            "/webhooks/voice", data=CALL_PARAMS, headers={"X-Twilio-Signature": "sig"}
        )

    assert response.status_code == 404
    assert call_session_repo.sessions == {}


async def test_missing_call_params_is_rejected():
    conn_repo = FakeChannelConnectionRepo(resolution=make_channel_resolution(channel_type="voice"))
    app_repo = FakeChannelAppRepo(channel_app=_channel_app())
    call_session_repo = FakeCallSessionRepo()
    voice_provider = FakeVoiceProvider(signature_valid=True)

    async with client_for_router(
        router,
        channel_connection_repo=conn_repo,
        channel_app_repo=app_repo,
        call_session_repo=call_session_repo,
        voice_provider=voice_provider,
    ) as client:
        response = await client.post(
            "/webhooks/voice", data={"To": "+15559998888"}, headers={"X-Twilio-Signature": "sig"}
        )

    assert response.status_code == 400
