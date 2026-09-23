"""Admin endpoints for a tenant's billing profile.

Separate from `admin/tenants.py` on purpose: a distinct resource in `POLICY`
(`tenant_billing`, `admin`/`tenant_manager` only - `botmaster` manages agents
and channels, not billing). A client's own read-only view of the same data
goes through `GET /me/billing-profile` instead (see `adapters/inbound/http/me.py`),
never this admin API.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import TenantBillingOut, TenantBillingUpdate

router = APIRouter(prefix="/tenants", tags=["admin:tenant-billing"])


async def _existing_tenant(request: Request, access: AdminAccess, tenant_id: UUID) -> None:
    """Require a tenant that exists AND is inside the caller's scope.

    `access.tenant()` alone is not enough: for an unrestricted caller (admin,
    API key) it only checks scope (always true) and never looks the id up,
    so a made-up id would otherwise sail through into `get_by_id`/`upsert` -
    see `admin/tenants.py`'s own `get_tenant` for the same two-step pattern.

    Args:
        request (Request): Used to reach `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller.
        tenant_id (UUID): Tenant to check.

    Raises:
        HTTPException: 404 if it does not exist or is out of scope.
    """
    access.tenant(tenant_id)
    if not await request.app.state.tenant_repo.get_by_id(tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")


@router.get("/{tenant_id}/billing", response_model=TenantBillingOut)
async def get_tenant_billing(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("tenant_billing", "read"))
) -> TenantBillingOut:
    """Fetch a tenant's billing profile, creating an empty one if none exists yet.

    Args:
        tenant_id (UUID): Id of the tenant.
        request (Request): Used to reach `request.app.state.tenant_billing_profile_repo`.
        access (AdminAccess): The authenticated caller (admin/tenant_manager,
            scoped to their own tenants).

    Returns:
        TenantBillingOut: The profile - all fields `None` if nothing was
        ever filled in.

    Raises:
        HTTPException: 404 if the tenant does not exist or is out of scope.
    """
    await _existing_tenant(request, access, tenant_id)
    repo = request.app.state.tenant_billing_profile_repo
    profile = await repo.get_by_tenant_id(tenant_id)
    if profile is None:
        # Se persiste ya vacía: simplifica el PUT posterior (siempre hay una fila que actualizar).
        profile = await repo.upsert(tenant_id)
    return TenantBillingOut(**profile.model_dump())


@router.put("/{tenant_id}/billing", response_model=TenantBillingOut)
async def upsert_tenant_billing(
    tenant_id: UUID,
    body: TenantBillingUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("tenant_billing", "write")),
) -> TenantBillingOut:
    """Create or update a tenant's billing profile.

    Args:
        tenant_id (UUID): Id of the tenant.
        body (TenantBillingUpdate): Fields to set; unset fields are left
            unchanged (or empty, on first creation).
        request (Request): Used to reach `request.app.state.tenant_billing_profile_repo`.
        access (AdminAccess): The authenticated caller (admin/tenant_manager,
            scoped to their own tenants).

    Returns:
        TenantBillingOut: The resulting profile.

    Raises:
        HTTPException: 404 if the tenant does not exist or is out of scope.
    """
    await _existing_tenant(request, access, tenant_id)
    repo = request.app.state.tenant_billing_profile_repo
    profile = await repo.upsert(tenant_id, **body.model_dump(exclude_unset=True))
    return TenantBillingOut(**profile.model_dump())
