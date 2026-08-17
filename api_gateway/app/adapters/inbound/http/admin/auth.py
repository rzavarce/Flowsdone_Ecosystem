"""Shared authentication dependency for the admin HTTP API."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from api_gateway.app.core.config import settings


async def require_admin_api_key(x_admin_api_key: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency that enforces the admin API key header.

    Args:
        x_admin_api_key (Optional[str]): Value of the X-Admin-Api-Key header.

    Raises:
        HTTPException: 401 if the header is missing or does not match
            settings.ADMIN_API_KEY.
    """
    if not settings.ADMIN_API_KEY or x_admin_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="invalid admin api key")
