from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException
from starlette.responses import PlainTextResponse


def verify_meta_signature(raw_body: bytes, signature_header: Optional[str], app_secret: str) -> bool:
    """
    Valida el header X-Hub-Signature-256 que Meta (Facebook/Instagram Graph
    API) envía en cada webhook POST: sha256=<HMAC-SHA256(app_secret, raw_body)>.
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
    """
    Maneja el GET de suscripción de un webhook de Meta (mismo mecanismo para
    Facebook Messenger e Instagram, comparten una única Meta App).
    """
    if mode == "subscribe" and challenge and expected_token and verify_token == expected_token:
        return PlainTextResponse(content=challenge, status_code=200)

    raise HTTPException(status_code=403, detail="webhook verification failed")
