"""Tests for HttpCallbackSender: SSRF guard, allow-list, signature, retries."""

from __future__ import annotations

import json
import socket

import pytest

from app.adapters.outbound.http import callback_sender as module
from app.adapters.outbound.http.callback_sender import (
    SIGNATURE_HEADER,
    HttpCallbackSender,
    build_callback_sender,
    parse_allowed_hosts,
)
from app.application.services.hmac_signing import verify
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio

SECRET = "s3cret"


@pytest.fixture
def client(monkeypatch):
    fake = FakeAsyncClient(lambda call: FakeResponse(200))
    monkeypatch.setattr(module.httpx, "AsyncClient", fake.as_constructor())

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    return fake


def resolving_to(monkeypatch, *addresses):
    async def fake_resolve(host, port):
        return list(addresses)

    monkeypatch.setattr(HttpCallbackSender, "_resolve", staticmethod(fake_resolve))


async def test_a_public_https_callback_is_sent_signed(client, monkeypatch):
    resolving_to(monkeypatch, "93.184.216.34")

    ok = await HttpCallbackSender(secret=SECRET).send("https://hooks.example.com/cb", {"message": "hola"})

    assert ok is True
    [call] = client.calls
    body = call.kwargs["content"]
    assert json.loads(body) == {"message": "hola"}
    assert verify(body, call.kwargs["headers"][SIGNATURE_HEADER], SECRET)


@pytest.mark.parametrize(
    "url, addresses",
    [
        ("http://hooks.example.com/cb", ["93.184.216.34"]),  # plain http
        ("https://internal.example.com/cb", ["10.0.0.5"]),  # private
        ("https://localhost/cb", ["127.0.0.1"]),  # loopback
        ("https://metadata.example.com/cb", ["169.254.169.254"]),  # link-local (cloud metadata)
        ("https://v6.example.com/cb", ["::1"]),  # IPv6 loopback
        ("https://mapped.example.com/cb", ["::ffff:192.168.1.10"]),  # IPv4-mapped private
        ("https://mixed.example.com/cb", ["93.184.216.34", "172.18.0.9"]),  # one internal address is enough
        ("https://user:pass@hooks.example.com/cb", ["93.184.216.34"]),  # credentials in the URL
        ("ftp://hooks.example.com/cb", ["93.184.216.34"]),
    ],
)
async def test_unsafe_destinations_are_refused(client, monkeypatch, url, addresses):
    resolving_to(monkeypatch, *addresses)

    assert await HttpCallbackSender(secret=SECRET).send(url, {"message": "hola"}) is False
    assert client.calls == []


async def test_an_unresolvable_host_is_refused(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise socket.gaierror("nope")

    class Loop:
        getaddrinfo = staticmethod(fail)

    monkeypatch.setattr(module.asyncio, "get_running_loop", lambda: Loop())

    assert await HttpCallbackSender(secret=SECRET).send("https://nowhere.invalid/cb", {}) is False
    assert client.calls == []


async def test_allowed_hosts_may_be_internal_and_plain_http(client):
    sender = HttpCallbackSender(secret=SECRET, allowed_hosts=["n8n"])

    assert await sender.send("http://n8n:5678/webhook/result", {"message": "hola"}) is True
    assert await sender.send("https://hooks.example.com/cb", {"message": "hola"}) is False
    assert [c.url for c in client.calls] == ["http://n8n:5678/webhook/result"]


async def test_redirects_are_not_followed(monkeypatch):
    seen = {}

    fake = FakeAsyncClient(lambda call: FakeResponse(302))

    def constructor(*args, **kwargs):
        seen.update(kwargs)
        return fake

    monkeypatch.setattr(module.httpx, "AsyncClient", constructor)
    sender = HttpCallbackSender(secret=SECRET, allowed_hosts=["n8n"])

    assert await sender.send("http://n8n/cb", {}) is False
    assert seen["follow_redirects"] is False


async def test_server_errors_are_retried_and_client_errors_are_not(client, monkeypatch):
    statuses = iter([503, 200])
    client._response_factory = lambda call: FakeResponse(next(statuses))
    sender = HttpCallbackSender(secret=SECRET, allowed_hosts=["n8n"], max_retries=3)
    assert await sender.send("http://n8n/cb", {}) is True
    assert len(client.calls) == 2

    client.calls.clear()
    client._response_factory = lambda call: FakeResponse(404)
    assert await sender.send("http://n8n/cb", {}) is False
    assert len(client.calls) == 1


def test_settings_build_the_sender():
    class Settings:
        CALLBACK_HMAC_SECRET = SECRET
        CALLBACK_ALLOWED_HOSTS = " n8n, hooks.example.com ,"
        CALLBACK_MAX_RETRIES = 2
        CALLBACK_BACKOFF_SECONDS = 1

    sender = build_callback_sender(Settings())

    assert sender._allowed == {"n8n", "hooks.example.com"}
    assert parse_allowed_hosts("") == [] and parse_allowed_hosts(None) == []
