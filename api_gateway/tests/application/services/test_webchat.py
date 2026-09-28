"""Tests for the web chat rules: allowed origins and demo test tokens."""

from __future__ import annotations

import pytest

from app.application.services.webchat import (
    InvalidOriginError,
    TestTokenClaims,
    normalize_origins,
    origin_allowed,
    sign_test_token,
    verify_test_token,
)


def test_origins_are_normalized_and_deduplicated():
    assert normalize_origins([" Cliente.ES/contacto ", "https://cliente.es", "http://localhost:5173/x", "", None]) == [
        "https://cliente.es", "http://localhost:5173",
    ]
    assert normalize_origins(None) == []
    for bad in ("ftp://cliente.es", "mailto:x", "https://"):
        with pytest.raises(InvalidOriginError):
            normalize_origins([bad])


def test_empty_allows_any_origin_otherwise_only_the_listed_ones():
    assert origin_allowed([], None) and origin_allowed([], "https://x.com")
    assert origin_allowed(["https://cliente.es"], "https://cliente.es")
    assert not origin_allowed(["https://cliente.es"], "https://evil.es")
    assert not origin_allowed(["https://cliente.es"], None)
    assert not origin_allowed(["https://cliente.es"], "null")


def test_test_tokens_are_signed_and_expire():
    claims = TestTokenClaims(agent_id="a1", workflow_id="f1", expires_at=2_000)
    token = sign_test_token(claims, "secret")

    assert verify_test_token(token, "secret", now=1_000) == claims
    assert verify_test_token(token, "secret", now=2_001) is None  # expired
    assert verify_test_token(token, "other-secret", now=1_000) is None  # wrong key
    payload, signature = token.split(".")
    forged = sign_test_token(TestTokenClaims("a2", "f2", 2_000), "secret").split(".")[0]
    assert verify_test_token(f"{forged}.{signature}", "secret", now=1_000) is None  # tampered
    for junk in ("", "abc", "a.b.c", "!!.??"):
        assert verify_test_token(junk, "secret", now=1_000) is None
