"""Tests for the shared Meta webhook verification helpers
(Facebook + Instagram signature check and GET challenge)."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.adapters.inbound.http.channels.meta_common import (
    handle_verification_challenge,
    verify_meta_signature,
)


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestVerifyMetaSignature:
    def test_valid_signature_passes(self):
        body = b'{"entry": []}'
        signature = _sign("app-secret", body)

        assert verify_meta_signature(body, signature, "app-secret") is True

    def test_wrong_secret_fails(self):
        body = b'{"entry": []}'
        signature = _sign("app-secret", body)

        assert verify_meta_signature(body, signature, "different-secret") is False

    def test_tampered_body_fails(self):
        signature = _sign("app-secret", b'{"entry": []}')

        assert verify_meta_signature(b'{"entry": ["tampered"]}', signature, "app-secret") is False

    @pytest.mark.parametrize(
        "signature_header",
        [None, "", "not-prefixed-with-sha256=", "sha1=deadbeef"],
    )
    def test_missing_or_malformed_header_fails(self, signature_header):
        assert verify_meta_signature(b"body", signature_header, "app-secret") is False

    def test_missing_app_secret_fails(self):
        body = b"body"
        signature = _sign("whatever", body)

        assert verify_meta_signature(body, signature, "") is False


class TestHandleVerificationChallenge:
    def test_matching_token_echoes_challenge(self):
        response = handle_verification_challenge(
            mode="subscribe", verify_token="tok", challenge="the-challenge", expected_token="tok"
        )

        assert response.status_code == 200
        assert response.body == b"the-challenge"

    def test_wrong_token_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            handle_verification_challenge(
                mode="subscribe", verify_token="wrong", challenge="c", expected_token="tok"
            )

        assert exc_info.value.status_code == 403

    def test_wrong_mode_raises_403(self):
        with pytest.raises(HTTPException):
            handle_verification_challenge(
                mode="unsubscribe", verify_token="tok", challenge="c", expected_token="tok"
            )

    def test_no_expected_token_configured_raises_403(self):
        with pytest.raises(HTTPException):
            handle_verification_challenge(
                mode="subscribe", verify_token="tok", challenge="c", expected_token=None
            )
