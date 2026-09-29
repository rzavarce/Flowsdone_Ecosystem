"""Tests for MetaSenderProfileLookup: who wrote, for Messenger and Instagram."""

from __future__ import annotations

import pytest

from app.adapters.outbound.channels import meta_profile_lookup as module
from app.adapters.outbound.channels.meta_profile_lookup import MetaSenderProfileLookup
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio

CREDENTIALS = {"page_access_token": "TOKEN1"}


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "META_GRAPH_API_BASE_URL", "https://graph.facebook.com")
    monkeypatch.setattr(module.settings, "META_GRAPH_API_VERSION", "v21.0")


def _fake(monkeypatch, response):
    client = FakeAsyncClient(lambda call: response)
    monkeypatch.setattr(module.httpx, "AsyncClient", client.as_constructor())
    return client


async def test_a_messenger_sender_gets_their_name(monkeypatch):
    client = _fake(monkeypatch, FakeResponse(200, json_body={"first_name": "Ana", "last_name": "Pérez", "id": "psid-1"}))

    profile = await MetaSenderProfileLookup().lookup(channel_type="facebook", sender_id="psid-1", credentials=CREDENTIALS)

    assert profile.name == "Ana Pérez" and profile.username is None
    assert client.calls[0].url == "https://graph.facebook.com/v21.0/psid-1"
    assert client.calls[0].kwargs["params"] == {"fields": "first_name,last_name", "access_token": "TOKEN1"}


async def test_an_instagram_sender_gets_their_account_and_name(monkeypatch):
    client = _fake(monkeypatch, FakeResponse(200, json_body={"name": "Ana P", "username": "ana.p"}))

    profile = await MetaSenderProfileLookup().lookup(channel_type="instagram", sender_id="igsid-1", credentials=CREDENTIALS)

    assert (profile.name, profile.username) == ("Ana P", "@ana.p")
    assert client.calls[0].kwargs["params"]["fields"] == "name,username"


async def test_failures_and_other_channels_give_nothing(monkeypatch):
    client = _fake(monkeypatch, FakeResponse(403, text="no permission"))
    lookup = MetaSenderProfileLookup()

    assert await lookup.lookup(channel_type="facebook", sender_id="psid-1", credentials=CREDENTIALS) is None
    assert await lookup.lookup(channel_type="facebook", sender_id="psid-1", credentials={}) is None
    assert await lookup.lookup(channel_type="telegram", sender_id="7", credentials=CREDENTIALS) is None
    assert len(client.calls) == 1
