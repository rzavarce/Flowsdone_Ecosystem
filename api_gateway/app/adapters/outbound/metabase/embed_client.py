"""Metabase implementation of DashboardEmbedPort ("static embedding").

A dashboard is shown through `{METABASE_PUBLIC_URL}/embed/dashboard/<JWT>`.
The JWT, signed with the secret shared with Metabase, names the dashboard
and fixes its locked filters - here `tenant` - so the browser cannot change
them. The dashboards are created by scripts/metabase/provision.py, which
tags each one with `[flowsdone:<key>]` in its description; the adapter finds
their ids through Metabase's API (admin account) and keeps them in memory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Optional, Sequence

import httpx

from app.core.config import settings
from app.domain.ports.outbound.analytics import AnalyticsUnavailableError, DashboardEmbedPort

logger = logging.getLogger("metabase.embed_client")

COLLECTION = "Consola Flowsdone (gestionado)"
# Embedded look: no border, no Metabase title (the console shows its own).
EMBED_OPTIONS = "bordered=false&titled=false"
_ID_CACHE_SECONDS = 600


def _b64(data: bytes) -> str:
    """Base64url without padding (JWT encoding).

    Args:
        data (bytes): Raw bytes.

    Returns:
        str: Encoded text.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_jwt(payload: Dict, secret: str) -> str:
    """HS256 JWT, the format Metabase expects for embedding.

    Args:
        payload (Dict): Claims.
        secret (str): Shared secret (MB_EMBEDDING_SECRET_KEY).

    Returns:
        str: The token.
    """
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(signature)}"


class MetabaseEmbedAdapter(DashboardEmbedPort):
    """Signs embed URLs for the console's Metabase dashboards."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        """Build the adapter.

        Args:
            client (Optional[httpx.AsyncClient]): Client pointing at
                Metabase's internal URL; created from settings when omitted.
        """
        self._client = client or httpx.AsyncClient(base_url=settings.METABASE_INTERNAL_URL, timeout=15.0)
        self._session: Optional[str] = None
        self._ids: Dict[str, int] = {}
        self._ids_loaded_at = 0.0

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def embed_url(self, dashboard_key: str, *, tenant_ids: Sequence[str], ttl_seconds: int) -> str:
        """URL of a dashboard locked to `tenant_ids` (see the port).

        Args:
            dashboard_key (str): Which dashboard.
            tenant_ids (Sequence[str]): Tenants whose data it shows; empty = all.
            ttl_seconds (int): Validity of the URL.

        Returns:
            str: The embed URL.

        Raises:
            AnalyticsUnavailableError: If not configured, unreachable, or the
                dashboard does not exist.
        """
        secret = settings.METABASE_EMBEDDING_SECRET_KEY
        if not secret:
            raise AnalyticsUnavailableError("METABASE_EMBEDDING_SECRET_KEY is not configured")
        dashboard_id = await self._dashboard_id(dashboard_key)
        token = sign_jwt(
            {
                "resource": {"dashboard": dashboard_id},
                "params": {"tenant": list(tenant_ids)},
                "exp": int(time.time()) + ttl_seconds,
            },
            secret,
        )
        return f"{settings.METABASE_PUBLIC_URL}/embed/dashboard/{token}#{EMBED_OPTIONS}"

    async def _dashboard_id(self, key: str) -> int:
        """Id of the dashboard tagged `[flowsdone:<key>]` (cached).

        Args:
            key (str): Dashboard key.

        Returns:
            int: Metabase dashboard id.

        Raises:
            AnalyticsUnavailableError: If it cannot be found.
        """
        fresh = time.monotonic() - self._ids_loaded_at < _ID_CACHE_SECONDS
        if key not in self._ids or not fresh:
            self._ids = await self._load_ids()
            self._ids_loaded_at = time.monotonic()
        if key not in self._ids:
            raise AnalyticsUnavailableError(f"dashboard {key!r} not found in Metabase (run provision.py)")
        return self._ids[key]

    async def _load_ids(self) -> Dict[str, int]:
        """Read the managed collection and map each tagged dashboard.

        Returns:
            Dict[str, int]: Dashboard id by key.

        Raises:
            AnalyticsUnavailableError: If Metabase fails.
        """
        collections = await self._get("/api/collection")
        managed = next((c for c in collections if c.get("name") == COLLECTION and not c.get("archived")), None)
        if managed is None:
            raise AnalyticsUnavailableError("the managed dashboards collection does not exist (run provision.py)")
        items = await self._get(f"/api/collection/{managed['id']}/items", params={"models": "dashboard"})
        ids: Dict[str, int] = {}
        for item in items:
            description = item.get("description") or ""
            start = description.find("[flowsdone:")
            if start != -1:
                ids[description[start + len("[flowsdone:"):description.index("]", start)]] = int(item["id"])
        return ids

    async def _get(self, path: str, params: Optional[Dict] = None) -> list:
        """GET as the admin, logging in (again) when needed.

        Args:
            path (str): API path.
            params (Optional[Dict]): Query string.

        Returns:
            list: The items (Metabase wraps some lists in {"data": [...]}).

        Raises:
            AnalyticsUnavailableError: If Metabase is down or refuses.
        """
        for attempt in (1, 2):
            if self._session is None:
                await self._login()
            try:
                response = await self._client.get(path, params=params, headers={"X-Metabase-Session": self._session or ""})
            except httpx.HTTPError as exc:
                raise AnalyticsUnavailableError(f"metabase unreachable: {exc.__class__.__name__}") from exc
            if response.status_code == 401 and attempt == 1:
                self._session = None
                continue
            if response.status_code != 200:
                raise AnalyticsUnavailableError(f"metabase answered HTTP {response.status_code} on {path}")
            body = response.json()
            return body.get("data", []) if isinstance(body, dict) else body
        raise AnalyticsUnavailableError("metabase refused the admin session")

    async def _login(self) -> None:
        """Open an admin session.

        Raises:
            AnalyticsUnavailableError: If not configured or refused.
        """
        if not (settings.METABASE_ADMIN_EMAIL and settings.METABASE_ADMIN_PASSWORD):
            raise AnalyticsUnavailableError("METABASE_ADMIN_EMAIL/METABASE_ADMIN_PASSWORD are not configured")
        try:
            response = await self._client.post(
                "/api/session",
                json={"username": settings.METABASE_ADMIN_EMAIL, "password": settings.METABASE_ADMIN_PASSWORD},
            )
        except httpx.HTTPError as exc:
            raise AnalyticsUnavailableError(f"metabase unreachable: {exc.__class__.__name__}") from exc
        if response.status_code != 200:
            logger.warning("metabase.login_refused", extra={"status_code": response.status_code})
            raise AnalyticsUnavailableError(f"metabase refused the admin login (HTTP {response.status_code})")
        self._session = response.json()["id"]
