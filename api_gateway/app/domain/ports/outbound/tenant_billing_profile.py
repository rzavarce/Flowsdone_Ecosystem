"""Port for persisting a tenant's billing profile."""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from app.domain.models.tenant_billing_profile import TenantBillingProfile


class TenantBillingProfileRepositoryPort(Protocol):
    """Persistence contract for `TenantBillingProfile` (1:1 with a tenant)."""

    async def get_by_tenant_id(self, tenant_id: UUID) -> Optional[TenantBillingProfile]:
        """Fetch a tenant's billing profile.

        Args:
            tenant_id (UUID): The tenant.

        Returns:
            Optional[TenantBillingProfile]: The profile, or None if the
            tenant doesn't have one yet (nothing filled in).
        """
        ...

    async def upsert(self, tenant_id: UUID, **fields: object) -> TenantBillingProfile:
        """Create or update a tenant's billing profile.

        Args:
            tenant_id (UUID): The tenant.
            **fields (object): Fields to set (`None` means "leave unset" on
                an update, or "no value" on a fresh create).

        Returns:
            TenantBillingProfile: The resulting profile.
        """
        ...
