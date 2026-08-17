"""Tests for X/Twitter's CRC/signature verification helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from app.adapters.inbound.http.channels.twitter import (
    _hmac_sha256_base64,
    _verify_signature,
)


def _sign(secret: str, message: bytes) -> str:
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return "sha256=" + base64.b64encode(digest).decode()


def test_hmac_sha256_base64_matches_manual_computation():
    result = _hmac_sha256_base64("secret", "hello")

    expected = base64.b64encode(
        hmac.new(b"secret", b"hello", hashlib.sha256).digest()
    ).decode()
    assert result == expected


def test_verify_signature_accepts_valid_signature():
    body = b'{"direct_message_events": []}'
    signature = _sign("consumer-secret", body)

    assert _verify_signature(body, signature, "consumer-secret") is True


def test_verify_signature_rejects_wrong_secret():
    body = b'{"direct_message_events": []}'
    signature = _sign("consumer-secret", body)

    assert _verify_signature(body, signature, "wrong-secret") is False


@pytest.mark.parametrize("signature_header", [None, "", "no-prefix", "sha1=abc"])
def test_verify_signature_rejects_malformed_header(signature_header):
    assert _verify_signature(b"body", signature_header, "secret") is False


def test_verify_signature_rejects_missing_consumer_secret():
    signature = _sign("whatever", b"body")

    assert _verify_signature(b"body", signature, None) is False
