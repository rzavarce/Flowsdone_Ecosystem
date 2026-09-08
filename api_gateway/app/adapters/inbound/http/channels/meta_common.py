"""Shared webhook verification helpers for Facebook and Instagram (Meta)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException
from starlette.responses import PlainTextResponse


def verify_meta_signature(raw_body: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """Validate the X-Hub-Signature-256 header Meta sends on every webhook POST.

    Args:
        raw_body (bytes): Raw request body bytes.
        signature_header (Optional[str]): Value of the
            X-Hub-Signature-256 header, expected as
            "sha256=<HMAC-SHA256(app_secret, raw_body)>".
        app_secret (str): The app secret to validate against.

    Returns:
        bool: True if the signature is present and valid.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not app_secret:
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def handle_verification_challenge(
    mode: Optional[str],
    verify_token: Optional[str],
    challenge: Optional[str],
    expected_token: Optional[str],
) -> PlainTextResponse:
    """Handle a Meta webhook subscription GET challenge.

    Same mechanism for both Facebook Messenger and Instagram, which
    share a single Meta app.

    Args:
        mode (Optional[str]): Value of the "hub.mode" query parameter.
        verify_token (Optional[str]): Value of the "hub.verify_token"
            query parameter.
        challenge (Optional[str]): Value of the "hub.challenge" query
            parameter.
        expected_token (Optional[str]): The verify token configured
            for this app.

    Returns:
        PlainTextResponse: Echoes the challenge if verification succeeds.

    Raises:
        HTTPException: 403 if verification fails.
    """
    if mode == "subscribe" and challenge and expected_token and verify_token == expected_token:
        return PlainTextResponse(content=challenge, status_code=200)

    raise HTTPException(status_code=403, detail="webhook verification failed")
