"""Tests for send_meta_message, shared by FacebookSender and InstagramSender."""

from __future__ import annotations

import pytest

from app.adapters.outbound.channels import meta_sender as module
from app.adapters.outbound.channels.facebook_sender import FacebookSender
from app.adapters.outbound.channels.instagram_sender import InstagramSender
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "META_GRAPH_API_BASE_URL", "https://graph.facebook.com")
    monkeypatch.setattr(module.settings, "META_GRAPH_API_VERSION", "v21.0")


@pytest.mark.parametrize("sender_cls", [FacebookSender, InstagramSender])
async def test_sends_message_with_page_access_token(monkeypatch, sender_cls):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await sender_cls().send(
        external_id="PAGE1",
        recipient_id="psid-1",
        text="hola",
        credentials={"page_access_token": "TOKEN1"},
    )

    call = fake_client.calls[0]
    assert call.url == "https://graph.facebook.com/v21.0/PAGE1/messages"
    assert call.kwargs["params"] == {"access_token": "TOKEN1"}
    assert call.kwargs["json"] == {"recipient": {"id": "psid-1"}, "message": {"text": "hola"}}


async def test_does_not_call_graph_api_when_page_access_token_missing(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await FacebookSender().send(
        external_id="PAGE1", recipient_id="psid-1", text="hola", credentials={}
    )

    assert fake_client.calls == []


async def test_does_not_raise_when_graph_api_rejects_the_send(monkeypatch):
    fake_client = FakeAsyncClient(lambda call: FakeResponse(400, text="bad request"))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())

    await FacebookSender().send(
        external_id="PAGE1",
        recipient_id="psid-1",
        text="hola",
        credentials={"page_access_token": "TOKEN1"},
    )
