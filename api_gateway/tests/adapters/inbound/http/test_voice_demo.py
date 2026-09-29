"""HTTP tests for GET /voice-demo/token: a Twilio token and the number to
call, only for a valid demo link."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from app.adapters.inbound.http.voice_demo import router
from app.application.use_cases.voice_demo import VoiceDemoTarget
from app.core.config import settings
from api_gateway.tests.support.asgi import client_for_router

pytestmark = pytest.mark.anyio


class FakeTarget:
    def __init__(self, target):
        self.target = target
        self.calls = []

    async def execute(self, *, share_token=None, test_token=None):
        self.calls.append(dict(share_token=share_token, test_token=test_token))
        return self.target


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_DEMO_TWILIO_ACCOUNT_SID", "AC" + "0" * 32)
    monkeypatch.setattr(settings, "VOICE_DEMO_TWILIO_API_KEY_SID", "SK" + "0" * 32)
    monkeypatch.setattr(settings, "VOICE_DEMO_TWILIO_API_KEY_SECRET", "secret")
    monkeypatch.setattr(settings, "VOICE_DEMO_TWILIO_TWIML_APP_SID", "AP" + "0" * 32)


async def test_a_valid_link_gets_a_token_and_the_number(configured):
    fake = FakeTarget(VoiceDemoTarget(agent_id=uuid4(), to_number="+16014944500"))
    async with client_for_router(router, voice_demo_target_use_case=fake) as client:
        response = await client.get("/voice-demo/token", params={"share": "tok", "identity": "demo-abc"})

    assert response.status_code == 200
    body = response.json()
    assert body["to_number"] == "+16014944500" and body["identity"] == "demo-abc"
    claims = jwt.decode(body["token"], "secret", algorithms=["HS256"])
    assert claims["grants"]["voice"]["outgoing"]["application_sid"] == "AP" + "0" * 32
    assert fake.calls == [dict(share_token="tok", test_token=None)]


async def test_no_valid_link_no_token(configured):
    async with client_for_router(router, voice_demo_target_use_case=FakeTarget(None)) as client:
        without = await client.get("/voice-demo/token")
        invalid = await client.get("/voice-demo/token", params={"test_token": "x"})

    assert without.status_code == 404 and invalid.status_code == 404
    assert "token" not in without.json()


async def test_unconfigured_voice_demo_is_a_404(monkeypatch):
    monkeypatch.setattr(settings, "VOICE_DEMO_TWILIO_ACCOUNT_SID", None)
    fake = FakeTarget(VoiceDemoTarget(agent_id=uuid4(), to_number="+1"))
    async with client_for_router(router, voice_demo_target_use_case=fake) as client:
        response = await client.get("/voice-demo/token", params={"share": "tok"})

    assert response.status_code == 404 and fake.calls == []


async def test_a_malformed_identity_is_refused(configured):
    fake = FakeTarget(VoiceDemoTarget(agent_id=uuid4(), to_number="+1"))
    async with client_for_router(router, voice_demo_target_use_case=fake) as client:
        response = await client.get("/voice-demo/token", params={"share": "tok", "identity": "<script>"})

    assert response.status_code == 422
