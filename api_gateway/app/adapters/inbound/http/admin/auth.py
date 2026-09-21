"""Shared authentication dependency for the admin HTTP API."""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


def is_valid_admin_api_key(value: Optional[str]) -> bool:
    """Check an `X-Admin-Api-Key` value in constant time.

    Args:
        value (Optional[str]): The header value, if present.

    Returns:
        bool: True only if it equals `settings.ADMIN_API_KEY` (which must be
        non-empty). Uses `hmac.compare_digest` so the comparison does not
        leak how many leading characters matched.
    """
    if not settings.ADMIN_API_KEY or value is None:
        return False
    return hmac.compare_digest(value.encode("utf-8"), settings.ADMIN_API_KEY.encode("utf-8"))


async def require_admin_api_key(x_admin_api_key: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency that enforces the admin API key header.

    Args:
        x_admin_api_key (Optional[str]): Value of the X-Admin-Api-Key header.

    Raises:
        HTTPException: 401 if the header is missing or does not match
            settings.ADMIN_API_KEY.
    """
    if not is_valid_admin_api_key(x_admin_api_key):
        raise HTTPException(status_code=401, detail="invalid admin api key")
