"""Tests for MetabaseEmbedAdapter (Metabase answered by an httpx MockTransport)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.adapters.outbound.metabase.embed_client import COLLECTION, MetabaseEmbedAdapter, sign_jwt
from app.core.config import settings
from app.domain.ports.outbound import AnalyticsUnavailableError

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "METABASE_EMBEDDING_SECRET_KEY", "s3cret")
    monkeypatch.setattr(settings, "METABASE_PUBLIC_URL", "https://bi.flowsdone.com")
    monkeypatch.setattr(settings, "METABASE_ADMIN_EMAIL", "admin@flowsdone.com")
    monkeypatch.setattr(settings, "METABASE_ADMIN_PASSWORD", "pw")


def _decode(token):
    header, body, signature = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    expected = hmac.new(b"s3cret", f"{header}.{body}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(pad(signature)) == expected
    return json.loads(base64.urlsafe_b64decode(pad(body)))


class FakeMetabase:
    def __init__(self, dashboards=None):
        self.dashboards = dashboards if dashboards is not None else [
            {"id": 3, "description": "Rendimiento. [flowsdone:platform]"},
            {"id": 5, "description": "Tu asistente [flowsdone:client]"},
            {"id": 9, "description": "hecho a mano"},
        ]
        self.calls: list = []
        self.expire_session = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"id": "sess"})
        if self.expire_session:
            self.expire_session = False
            return httpx.Response(401)
        if request.headers.get("x-metabase-session") != "sess":
            return httpx.Response(401)
        if request.url.path == "/api/collection":
            return httpx.Response(200, json=[{"id": 1, "name": "Otra"}, {"id": 7, "name": COLLECTION}])
        if request.url.path == "/api/collection/7/items":
            return httpx.Response(200, json={"data": self.dashboards})
        return httpx.Response(404)


def _adapter(fake):
    return MetabaseEmbedAdapter(httpx.AsyncClient(base_url="http://metabase:3000", transport=httpx.MockTransport(fake.handle)))


def test_sign_jwt_is_standard_hs256():
    token = sign_jwt({"a": 1}, "s3cret")
    assert _decode(token) == {"a": 1}
    assert json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "==")) == {"alg": "HS256", "typ": "JWT"}


async def test_builds_a_signed_url_with_the_tenant_locked():
    fake = FakeMetabase()
    url = await _adapter(fake).embed_url("client", tenant_ids=["t-1"], ttl_seconds=600)

    assert url.startswith("https://bi.flowsdone.com/embed/dashboard/") and url.endswith("#bordered=false&titled=false")
    claims = _decode(url.split("/embed/dashboard/")[1].split("#")[0])
    assert claims["resource"] == {"dashboard": 5} and claims["params"] == {"tenant": ["t-1"]}
    assert claims["exp"] > 0


async def test_dashboard_ids_are_cached_and_a_stale_session_is_renewed():
    fake = FakeMetabase()
    adapter = _adapter(fake)
    await adapter.embed_url("platform", tenant_ids=[], ttl_seconds=60)
    fake.calls.clear()
    await adapter.embed_url("client", tenant_ids=[], ttl_seconds=60)
    assert fake.calls == []  # both ids came with the first listing

    adapter._ids_loaded_at = time.monotonic() - 3600  # cache expired (an hour ago)
    fake.expire_session = True
    await adapter.embed_url("platform", tenant_ids=[], ttl_seconds=60)
    assert ("POST", "/api/session") in fake.calls


async def test_unknown_dashboard_missing_config_or_metabase_down_are_unavailable(monkeypatch):
    with pytest.raises(AnalyticsUnavailableError, match="reports"):
        await _adapter(FakeMetabase()).embed_url("reports", tenant_ids=[], ttl_seconds=60)

    def down(request):
        raise httpx.ConnectError("down")

    adapter = MetabaseEmbedAdapter(httpx.AsyncClient(base_url="http://metabase:3000", transport=httpx.MockTransport(down)))
    with pytest.raises(AnalyticsUnavailableError, match="unreachable"):
        await adapter.embed_url("client", tenant_ids=[], ttl_seconds=60)

    monkeypatch.setattr(settings, "METABASE_EMBEDDING_SECRET_KEY", None)
    with pytest.raises(AnalyticsUnavailableError, match="SECRET"):
        await _adapter(FakeMetabase()).embed_url("client", tenant_ids=[], ttl_seconds=60)
