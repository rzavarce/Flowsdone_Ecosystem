"""Use case behind the console's Dashboard section: which dashboard each
profile sees, and over which tenants.

The tenant restriction is decided here and fixed in the signed URL (see
`DashboardEmbedPort`), so the viewer can never widen it:
- a tenant chosen in the console must be one of the user's own;
- with no tenant chosen, an admin sees every tenant and anybody else sees
  exactly their own tenants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

from app.application.dto.auth_dto import AuthenticatedUser
from app.domain.ports.outbound import DashboardEmbedPort

# Staff see the platform's performance and usage (admins also the business
# block); clients and consultants see their own assistants' activity.
DASHBOARD_BY_ROLE: Dict[str, str] = {
    "admin": "platform_admin",
    "tenant_manager": "platform",
    "botmaster": "platform",
    "client": "client",
    "consultant": "client",
}


class TenantOutOfScopeError(Exception):
    """The chosen tenant is not one of the user's (maps to 404)."""


class NoTenantsError(Exception):
    """A non-admin user without tenants has nothing to see (maps to 403)."""


@dataclass(frozen=True)
class DashboardEmbed:
    """A dashboard ready to show.

    Attributes:
        url (str): URL to load in an iframe.
        dashboard (str): Which dashboard it is.
        expires_in (int): Seconds the URL stays valid.
    """

    url: str
    dashboard: str
    expires_in: int


class GetOverviewDashboardUseCase:
    """The dashboard of the console's Dashboard section for a user."""

    def __init__(self, *, embeds: DashboardEmbedPort, ttl_seconds: int) -> None:
        """Build the use case.

        Args:
            embeds (DashboardEmbedPort): Builds the signed URLs.
            ttl_seconds (int): Validity of each URL.
        """
        self._embeds = embeds
        self._ttl = ttl_seconds

    async def execute(self, user: AuthenticatedUser, tenant_id: Optional[UUID] = None) -> DashboardEmbed:
        """Pick the dashboard and the tenants for `user`.

        Args:
            user (AuthenticatedUser): The signed-in user (with their tenants).
            tenant_id (Optional[UUID]): Tenant chosen in the console, if any.

        Returns:
            DashboardEmbed: The dashboard's URL.

        Raises:
            TenantOutOfScopeError: If `tenant_id` is not one of the user's.
            NoTenantsError: If a non-admin user has no tenants.
            AnalyticsUnavailableError: If the dashboards tool fails.
        """
        key = DASHBOARD_BY_ROLE[user.role]
        own = [str(tenant.id) for tenant in user.tenants]
        if tenant_id is not None:
            if str(tenant_id) not in own:
                raise TenantOutOfScopeError(str(tenant_id))
            tenants = [str(tenant_id)]
        elif user.role == "admin":
            tenants = []  # every tenant
        elif own:
            tenants = own
        else:
            raise NoTenantsError(str(user.id))
        url = await self._embeds.embed_url(key, tenant_ids=tenants, ttl_seconds=self._ttl)
        return DashboardEmbed(url=url, dashboard=key, expires_in=self._ttl)
