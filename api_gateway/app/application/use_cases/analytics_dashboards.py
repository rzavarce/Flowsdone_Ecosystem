"""Use cases behind the console's Dashboard and Reports sections: which
dashboards each profile sees, and over which tenants.

The tenant restriction is decided here and fixed in the signed URL (see
`DashboardEmbedPort`), so the viewer can never widen it:
- a tenant chosen in the console must be one of the user's own;
- with no tenant chosen, an admin sees every tenant and anybody else sees
  exactly their own tenants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
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


# Reports section, in display order. Staff with reports (admin, managers) and
# the client side see all of them; botmasters have no Reports section.
REPORT_KEYS: tuple[str, ...] = (
    "report_channels", "report_agents", "report_contacts", "report_hours", "report_usage",
)
REPORT_ROLES = frozenset({"admin", "tenant_manager", "client", "consultant"})


class ReportNotFoundError(Exception):
    """Unknown report, or not available to the user's profile (maps to 404)."""


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


def tenants_for(user: AuthenticatedUser, tenant_id: Optional[UUID]) -> List[str]:
    """The tenants a dashboard may show for `user` (locked in the signed URL).

    Args:
        user (AuthenticatedUser): The signed-in user (with their tenants).
        tenant_id (Optional[UUID]): Tenant chosen in the console, if any.

    Returns:
        List[str]: Tenant ids; empty means every tenant (admins only).

    Raises:
        TenantOutOfScopeError: If `tenant_id` is not one of the user's.
        NoTenantsError: If a non-admin user has no tenants.
    """
    own = [str(tenant.id) for tenant in user.tenants]
    if tenant_id is not None:
        if str(tenant_id) not in own:
            raise TenantOutOfScopeError(str(tenant_id))
        return [str(tenant_id)]
    if user.role == "admin":
        return []  # every tenant
    if own:
        return own
    raise NoTenantsError(str(user.id))


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
        tenants = tenants_for(user, tenant_id)
        url = await self._embeds.embed_url(key, tenant_ids=tenants, ttl_seconds=self._ttl)
        return DashboardEmbed(url=url, dashboard=key, expires_in=self._ttl)


class ReportsUseCase:
    """The Reports section: which reports a user has, and each one's URL."""

    def __init__(self, *, embeds: DashboardEmbedPort, ttl_seconds: int) -> None:
        """Build the use case.

        Args:
            embeds (DashboardEmbedPort): Builds the signed URLs.
            ttl_seconds (int): Validity of each URL.
        """
        self._embeds = embeds
        self._ttl = ttl_seconds

    @staticmethod
    def available(user: AuthenticatedUser) -> List[str]:
        """Reports the user's profile can open, in display order.

        Args:
            user (AuthenticatedUser): The signed-in user.

        Returns:
            List[str]: Report keys (empty for profiles without Reports).
        """
        return list(REPORT_KEYS) if user.role in REPORT_ROLES else []

    async def open(self, user: AuthenticatedUser, report: str, tenant_id: Optional[UUID] = None) -> DashboardEmbed:
        """URL of one report, locked to the allowed tenants.

        Args:
            user (AuthenticatedUser): The signed-in user.
            report (str): Report key.
            tenant_id (Optional[UUID]): Tenant chosen in the console, if any.

        Returns:
            DashboardEmbed: The report's URL.

        Raises:
            ReportNotFoundError: If the report does not exist or the profile has no reports.
            TenantOutOfScopeError: If `tenant_id` is not one of the user's.
            NoTenantsError: If a non-admin user has no tenants.
            AnalyticsUnavailableError: If the dashboards tool fails.
        """
        if report not in self.available(user):
            raise ReportNotFoundError(report)
        tenants = tenants_for(user, tenant_id)
        url = await self._embeds.embed_url(report, tenant_ids=tenants, ttl_seconds=self._ttl)
        return DashboardEmbed(url=url, dashboard=report, expires_in=self._ttl)
