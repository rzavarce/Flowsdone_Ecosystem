"""Port for the analytics dashboards shown inside the console.

The domain only knows it can get a short-lived URL for a named dashboard,
restricted to some tenants. Which tool draws it (Metabase) and how the
restriction is enforced (a signed token) are adapter concerns - see
`adapters/outbound/metabase/`.
"""

from __future__ import annotations

from typing import Protocol, Sequence


class AnalyticsUnavailableError(Exception):
    """The dashboards tool is not configured or not reachable (maps to 503)."""


class DashboardEmbedPort(Protocol):
    """Builds URLs that show one dashboard, locked to some tenants."""

    async def embed_url(self, dashboard_key: str, *, tenant_ids: Sequence[str], ttl_seconds: int) -> str:
        """URL of a dashboard whose data is limited to `tenant_ids`.

        The viewer cannot widen that restriction: it is part of the signed URL.

        Args:
            dashboard_key (str): Which dashboard ("platform", "client"…).
            tenant_ids (Sequence[str]): Tenants whose data it shows; empty
                means every tenant (only for callers that may see them all).
            ttl_seconds (int): How long the URL stays valid.

        Returns:
            str: The URL to load in an iframe.

        Raises:
            AnalyticsUnavailableError: If the tool is not configured, is
                down, or the dashboard does not exist.
        """
        ...
