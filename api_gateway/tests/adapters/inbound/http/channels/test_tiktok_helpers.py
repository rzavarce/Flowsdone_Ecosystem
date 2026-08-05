"""Tests for TikTok's webhook signature verification helper."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from api_gateway.app.adapters.inbound.http.channels.tiktok import _verify_signature


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    message = f"{timestamp}.{body.decode()}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},s={signature}"


def test_verify_signature_accepts_valid_signature():
    body = b'{"data": {}}'
    header = _sign("client-secret", "1700000000", body)

    assert _verify_signature(body, header, "client-secret") is True


def test_verify_signature_rejects_wrong_secret():
    body = b'{"data": {}}'
    header = _sign("client-secret", "1700000000", body)

    assert _verify_signature(body, header, "wrong-secret") is False


def test_verify_signature_rejects_tampered_body():
    header = _sign("client-secret", "1700000000", b'{"data": {}}')

    assert _verify_signature(b'{"data": {"tampered": true}}', header, "client-secret") is False


@pytest.mark.parametrize("header", [None, "", "malformed", "t=123"])
def test_verify_signature_rejects_malformed_header(header):
    assert _verify_signature(b"body", header, "client-secret") is False


def test_verify_signature_rejects_missing_client_secret():
    header = _sign("whatever", "123", b"body")

    assert _verify_signature(b"body", header, None) is False
