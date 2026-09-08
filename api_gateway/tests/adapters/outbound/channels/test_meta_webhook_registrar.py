"""Tests for MetaWebhookRegistrar (Facebook/Instagram page subscription)."""

from __future__ import annotations

import pytest

from app.adapters.outbound.channels import meta_webhook_registrar as module
from app.adapters.outbound.channels.meta_webhook_registrar import (
    MetaWebhookRegistrar,
    MetaWebhookRegistrationError,
)
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "META_GRAPH_API_BASE_URL", "https://graph.facebook.com")
    monkeypatch.setattr(module.settings, "META_GRAPH_API_VERSION", "v21.0")


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


def test_secret_field_is_none_meta_does_not_need_a_generated_secret():
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages")

    assert registrar.secret_field is None


async def test_register_subscribes_the_page_with_its_own_access_token(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"success": True}))
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages,messaging_postbacks")

    await registrar.register(external_id="PAGE123", credentials={"page_access_token": "TOKEN1"})

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call.method == "POST"
    assert call.url == "https://graph.facebook.com/v21.0/PAGE123/subscribed_apps"
    assert call.kwargs["params"] == {
        "access_token": "TOKEN1",
        "subscribed_fields": "messages,messaging_postbacks",
    }


async def test_deregister_unsubscribes_with_delete(monkeypatch):
    fake_client = _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"success": True}))
    registrar = MetaWebhookRegistrar(channel="instagram", subscribed_fields="messages")

    await registrar.deregister(external_id="PAGE123", credentials={"page_access_token": "TOKEN1"})

    assert fake_client.calls[0].method == "DELETE"
    assert fake_client.calls[0].kwargs["params"] == {"access_token": "TOKEN1"}


async def test_register_raises_when_page_access_token_missing(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"success": True}))
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages")

    with pytest.raises(MetaWebhookRegistrationError):
        await registrar.register(external_id="PAGE123", credentials={})


async def test_register_raises_when_graph_api_rejects_it(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(200, json_body={"success": False}))
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages")

    with pytest.raises(MetaWebhookRegistrationError):
        await registrar.register(external_id="PAGE123", credentials={"page_access_token": "BAD"})


async def test_register_raises_on_http_error_status(monkeypatch):
    _patch_client(monkeypatch, lambda call: FakeResponse(401, text="Unauthorized", headers={}))
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages")

    with pytest.raises(MetaWebhookRegistrationError):
        await registrar.register(external_id="PAGE123", credentials={"page_access_token": "BAD"})


async def test_register_raises_when_network_unreachable(monkeypatch):
    import httpx

    def _raise(_call):
        raise httpx.ConnectError("no network")

    _patch_client(monkeypatch, _raise)
    registrar = MetaWebhookRegistrar(channel="facebook", subscribed_fields="messages")

    with pytest.raises(MetaWebhookRegistrationError):
        await registrar.register(external_id="PAGE123", credentials={"page_access_token": "T"})
