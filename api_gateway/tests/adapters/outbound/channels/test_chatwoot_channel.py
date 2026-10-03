"""Tests for the Chatwoot outbound adapters (client, registrar, sender)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app.adapters.outbound.channels import chatwoot_api as module
from app.adapters.outbound.channels.chatwoot_api import ChatwootError
from app.adapters.outbound.channels.chatwoot_sender import ChatwootSender
from app.adapters.outbound.channels.chatwoot_webhook_registrar import ChatwootWebhookRegistrar
from app.domain.models.channel_app import ChannelApp
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse
from api_gateway.tests.support.fakes import FakeChannelAppRepo

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 3, tzinfo=timezone.utc)
API = "https://app.chatwoot.com/api/v1/accounts/7"


@pytest.fixture(autouse=True)
def _fixed_settings(monkeypatch):
    monkeypatch.setattr(module.settings, "PUBLIC_BASE_URL", "https://platform.example.com")


def _app(credentials=None, config=None):
    return ChannelApp(
        id=uuid4(),
        provider="chatwoot",
        credentials={"api_access_token": "ADMIN", "webhook_token": "WT", **(credentials or {})},
        config={"account_id": 7, **(config or {})},
        created_at=NOW,
        updated_at=NOW,
    )


def _patch_client(monkeypatch, response_factory):
    fake_client = FakeAsyncClient(response_factory)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


def _ok(json_body=None):
    return lambda call: FakeResponse(200, json_body=json_body or {})


async def test_the_first_inbox_creates_the_shared_bot_stores_it_and_assigns_it(monkeypatch):
    repo = FakeChannelAppRepo(_app())
    fake_client = _patch_client(
        monkeypatch,
        lambda call: FakeResponse(200, json_body={"id": 42, "access_token": "BOT"} if call.url.endswith("/agent_bots") else {}),
    )

    await ChatwootWebhookRegistrar(repo).register(external_id="15", credentials={})

    create, assign = fake_client.calls
    assert (create.method, create.url) == ("POST", f"{API}/agent_bots")
    assert create.kwargs["headers"] == {"api_access_token": "ADMIN"}
    assert create.kwargs["json"]["outgoing_url"] == "https://platform.example.com/webhooks/chatwoot?token=WT"
    assert assign.url == f"{API}/inboxes/15/set_agent_bot"
    assert assign.kwargs["json"] == {"agent_bot": 42}
    assert repo.channel_app.config["bot_id"] == 42
    assert repo.channel_app.credentials["bot_access_token"] == "BOT"


async def test_later_inboxes_reuse_the_bot(monkeypatch):
    repo = FakeChannelAppRepo(_app({"bot_access_token": "BOT"}, {"bot_id": 42}))
    fake_client = _patch_client(monkeypatch, _ok())

    await ChatwootWebhookRegistrar(repo).register(external_id="16", credentials={})

    assert [c.url for c in fake_client.calls] == [f"{API}/inboxes/16/set_agent_bot"]
    assert repo.upsert_calls == []


async def test_a_self_hosted_instance_uses_its_base_url(monkeypatch):
    repo = FakeChannelAppRepo(_app({"bot_access_token": "BOT"}, {"bot_id": 42, "base_url": "https://chat.example.com/"}))
    fake_client = _patch_client(monkeypatch, _ok())

    await ChatwootWebhookRegistrar(repo).register(external_id="16", credentials={})

    assert fake_client.calls[0].url == "https://chat.example.com/api/v1/accounts/7/inboxes/16/set_agent_bot"


async def test_deregister_unassigns_the_bot(monkeypatch):
    fake_client = _patch_client(monkeypatch, _ok())

    await ChatwootWebhookRegistrar(FakeChannelAppRepo(_app())).deregister(external_id="15", credentials={})

    assert fake_client.calls[0].kwargs["json"] == {"agent_bot": None}


@pytest.mark.parametrize("app", [None, _app(config={"account_id": None})])
async def test_registering_without_a_configured_app_fails_before_calling_chatwoot(monkeypatch, app):
    fake_client = _patch_client(monkeypatch, _ok())

    with pytest.raises(ChatwootError):
        await ChatwootWebhookRegistrar(FakeChannelAppRepo(app)).register(external_id="15", credentials={})

    assert fake_client.calls == []


@pytest.mark.parametrize("failure", ["status", "network"])
async def test_a_chatwoot_failure_surfaces_as_chatwoot_error(monkeypatch, failure):
    def _respond(_call):
        if failure == "network":
            raise httpx.ConnectError("down")
        return FakeResponse(401, text="unauthorized")

    _patch_client(monkeypatch, _respond)

    with pytest.raises(ChatwootError):
        await ChatwootWebhookRegistrar(FakeChannelAppRepo(_app())).register(external_id="15", credentials={})


async def test_replies_are_posted_to_the_conversation_as_the_bot(monkeypatch):
    fake_client = _patch_client(monkeypatch, _ok())
    sender = ChatwootSender(FakeChannelAppRepo(_app({"bot_access_token": "BOT"}, {"bot_id": 42})))

    await sender.send(external_id="15", recipient_id="981", text="hola", credentials={})

    call = fake_client.calls[0]
    assert call.url == f"{API}/conversations/981/messages"
    assert call.kwargs["headers"] == {"api_access_token": "BOT"}
    assert call.kwargs["json"] == {"content": "hola", "message_type": "outgoing", "private": False}


async def test_a_reply_before_the_bot_exists_is_logged_not_raised(monkeypatch, caplog):
    fake_client = _patch_client(monkeypatch, _ok())

    await ChatwootSender(FakeChannelAppRepo(_app())).send(external_id="15", recipient_id="981", text="x", credentials={})

    assert fake_client.calls == []
    assert any(r.levelname == "ERROR" for r in caplog.records)
