"""Shared HMAC-SHA256 signing/verification for internal, same-network
requests between gateway processes (e.g. a worker forwarding an
outbound envelope to /internal/outbound or /internal/voice callers).

Not used for verifying signatures from external providers (Meta,
Twilio, ...) - those follow each provider's own signature scheme.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def sign(body: bytes, secret: str) -> str:
    """Compute the HMAC-SHA256 signature of a request body.

    Args:
        body (bytes): Raw request body bytes.
        secret (str): Shared secret to sign with.

    Returns:
        str: The hex-encoded HMAC-SHA256 digest.
    """
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify(body: bytes, signature: Optional[str], secret: str) -> bool:
    """Verify an HMAC-SHA256 signature produced by `sign`.

    Args:
        body (bytes): Raw request body bytes, as received.
        signature (Optional[str]): Signature to verify, or None.
        secret (str): Shared secret the signature should have been
            computed with.

    Returns:
        bool: True if `signature` is present and matches.
    """
    if not signature:
        return False
    return hmac.compare_digest(sign(body, secret), signature)
