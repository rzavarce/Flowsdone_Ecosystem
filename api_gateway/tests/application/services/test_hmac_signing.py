"""Tests for the shared HMAC-SHA256 sign/verify helpers."""

from __future__ import annotations

from app.application.services.hmac_signing import sign, verify


def test_sign_is_deterministic_for_the_same_body_and_secret():
    body = b'{"hello":"world"}'
    assert sign(body, "s3cret") == sign(body, "s3cret")


def test_sign_differs_for_different_secrets():
    body = b'{"hello":"world"}'
    assert sign(body, "s3cret") != sign(body, "other")


def test_verify_accepts_a_valid_signature():
    body = b'{"hello":"world"}'
    signature = sign(body, "s3cret")

    assert verify(body, signature, "s3cret") is True


def test_verify_rejects_a_tampered_body():
    body = b'{"hello":"world"}'
    signature = sign(body, "s3cret")

    assert verify(b'{"hello":"mars"}', signature, "s3cret") is False


def test_verify_rejects_a_wrong_secret():
    body = b'{"hello":"world"}'
    signature = sign(body, "s3cret")

    assert verify(body, signature, "wrong-secret") is False


def test_verify_rejects_a_missing_signature():
    assert verify(b"body", None, "s3cret") is False
    assert verify(b"body", "", "s3cret") is False
