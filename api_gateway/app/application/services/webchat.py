"""Rules of the web chat: which websites may embed a tenant's chat, and the
signed tokens that let staff try any agent from the generic demo.

Two ways into the same WebSocket (see adapters/inbound/http/websocket.py):
- a tenant's **webchat channel**, by its public key (`wc_...`) - a normal
  channel: conversations, usage, plan limits and dashboards;
- a **test token**, issued to console staff for one agent, short-lived and
  signed - the demo page, whose conversations are not tracked nor billed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional
from urllib.parse import urlsplit


class InvalidOriginError(ValueError):
    """A value in allowed_origins is not a website origin (maps to 400)."""


def normalize_origin(value: str) -> str:
    """`https://Example.com/path` -> `https://example.com` (scheme + host[:port]).

    Args:
        value (str): What the user typed.

    Returns:
        str: The origin.

    Raises:
        InvalidOriginError: If it is not an http(s) URL with a host.
    """
    text = value.strip()
    if "://" not in text:
        text = f"https://{text}"
    try:
        parts = urlsplit(text)
        port = f":{parts.port}" if parts.port else ""
    except ValueError as exc:  # e.g. a port that is not a number
        raise InvalidOriginError(f"not a website origin: {value!r}") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise InvalidOriginError(f"not a website origin: {value!r}")
    return f"{parts.scheme}://{parts.hostname.lower()}{port}"


def normalize_origins(values: Optional[Iterable[Any]]) -> List[str]:
    """Normalize and de-duplicate a list of allowed origins, keeping order.

    Args:
        values (Optional[Iterable[Any]]): What the user typed (None = none).

    Returns:
        List[str]: Origins; empty means the chat may be embedded anywhere.

    Raises:
        InvalidOriginError: If one value is not a website origin.
    """
    result: List[str] = []
    for value in values or []:
        if not isinstance(value, str) or not value.strip():
            continue
        origin = normalize_origin(value)
        if origin not in result:
            result.append(origin)
    return result


def origin_allowed(allowed: Iterable[str], origin: Optional[str]) -> bool:
    """Whether a page at `origin` may use a webchat channel.

    Args:
        allowed (Iterable[str]): The channel's allowed origins (empty = any).
        origin (Optional[str]): The browser's `Origin` header.

    Returns:
        bool: True if allowed.
    """
    allowed = list(allowed)
    if not allowed:
        return True
    if not origin:
        return False
    try:
        return normalize_origin(origin) in allowed
    except InvalidOriginError:
        return False


@dataclass(frozen=True)
class TestTokenClaims:
    """What a demo test token grants.

    Attributes:
        agent_id (str): The agent under test.
        workflow_id (str): Its Langflow flow, where messages go.
        expires_at (int): Unix time after which the token is rejected.
    """

    agent_id: str
    workflow_id: str
    expires_at: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key(secret: str) -> bytes:
    """Derive the signing key, so the base secret is never used as-is.

    Args:
        secret (str): The gateway secret the key derives from.

    Returns:
        bytes: HMAC key for webchat test tokens only.
    """
    return hmac.new(secret.encode(), b"flowsdone:webchat-test-token:v1", hashlib.sha256).digest()


def sign_test_token(claims: TestTokenClaims, secret: str) -> str:
    """Sign a test token (`<payload>.<signature>`, base64url).

    Args:
        claims (TestTokenClaims): What it grants.
        secret (str): Gateway secret.

    Returns:
        str: The token.
    """
    payload = _b64(json.dumps({"a": claims.agent_id, "w": claims.workflow_id, "e": claims.expires_at},
                              separators=(",", ":")).encode())
    signature = _b64(hmac.new(_key(secret), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_test_token(token: str, secret: str, *, now: Optional[float] = None) -> Optional[TestTokenClaims]:
    """Check a test token.

    Args:
        token (str): The token.
        secret (str): Gateway secret.
        now (Optional[float]): Current Unix time (tests).

    Returns:
        Optional[TestTokenClaims]: The claims, or None if the token is
        malformed, forged or expired.
    """
    try:
        payload, signature = token.split(".")
        expected = _b64(hmac.new(_key(secret), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64(payload))
        claims = TestTokenClaims(agent_id=str(data["a"]), workflow_id=str(data["w"]), expires_at=int(data["e"]))
    except (ValueError, KeyError, TypeError):
        return None
    return claims if claims.expires_at > (now if now is not None else time.time()) else None
