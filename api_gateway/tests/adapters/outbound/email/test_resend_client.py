"""Tests for ResendEmailAdapter (Resend answered by an httpx MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.outbound.email.resend_client import ResendEmailAdapter
from app.core.config import settings
from app.domain.ports.outbound import EmailSendError

pytestmark = pytest.mark.anyio


def _adapter(handler) -> tuple[ResendEmailAdapter, list]:
    seen: list = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return ResendEmailAdapter(http), seen


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "no-reply@flowsdone.com")
    monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "Flowsdone")


async def test_sends_the_rendered_template_with_the_resend_key():
    adapter, seen = _adapter(lambda r: httpx.Response(200, json={"id": "email_1"}))

    await adapter.send_template(
        to="carla@cliente.com",
        template="account_activation",
        context={"name": "Carla", "link": "https://app.flowsdone.com/activar-cuenta/tok", "ttl_hours": 24},
        subject="Activa tu cuenta en Flowsdone",
    )

    assert len(seen) == 1
    request = seen[0]
    assert request.url == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer re_test_key"
    body = request.content.decode()
    assert '"to":["carla@cliente.com"]' in body.replace(" ", "")
    assert "Flowsdone <no-reply@flowsdone.com>" in body
    assert "Activa tu cuenta en Flowsdone" in body
    assert "https://app.flowsdone.com/activar-cuenta/tok" in body
    assert "Carla" in body


async def test_missing_api_key_fails_without_a_request():
    adapter, seen = _adapter(lambda r: httpx.Response(200, json={}))
    settings.RESEND_API_KEY = None

    with pytest.raises(EmailSendError, match="RESEND_API_KEY"):
        await adapter.send_template(to="a@b.com", template="account_activation", context={}, subject="s")
    assert seen == []


async def test_unknown_template_fails_without_a_request():
    adapter, seen = _adapter(lambda r: httpx.Response(200, json={}))

    with pytest.raises(EmailSendError, match="unknown email template"):
        await adapter.send_template(to="a@b.com", template="does-not-exist", context={}, subject="s")
    assert seen == []


async def test_resend_rejecting_the_email_raises():
    adapter, _ = _adapter(lambda r: httpx.Response(422, json={"message": "invalid `to` field"}))

    with pytest.raises(EmailSendError, match="422"):
        await adapter.send_template(
            to="a@b.com",
            template="password_reset",
            context={"name": "A", "link": "https://x", "ttl_hours": 1},
            subject="s",
        )


async def test_network_failure_raises():
    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    adapter, _ = _adapter(handler)

    with pytest.raises(EmailSendError, match="unreachable"):
        await adapter.send_template(
            to="a@b.com",
            template="password_reset",
            context={"name": "A", "link": "https://x", "ttl_hours": 1},
            subject="s",
        )
