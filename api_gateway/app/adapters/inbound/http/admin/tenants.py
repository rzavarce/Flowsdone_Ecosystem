"""Admin CRUD endpoints for tenants.

Reading is open to any staff role but scoped to the caller's own tenants;
creating, editing and deleting tenants is `admin` only (see `POLICY`).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["admin:tenants"])


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(
    body: TenantCreate, request: Request, access: AdminAccess = Depends(admin_access("tenants", "write"))
) -> TenantOut:
    """Create a tenant.

    Args:
        body (TenantCreate): Tenant fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        TenantOut: The created tenant.
    """
    tenant = await request.app.state.tenant_repo.create(name=body.name, slug=body.slug)
    return TenantOut(**tenant.model_dump())


@router.get("", response_model=list[TenantOut])
async def list_tenants(
    request: Request, access: AdminAccess = Depends(admin_access("tenants", "read"))
) -> list[TenantOut]:
    """List the tenants the caller can see.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[TenantOut]: Every tenant for admins and the API key; otherwise
        only the caller's own.
    """
    repo = request.app.state.tenant_repo
    if access.unrestricted:
        tenants = await repo.list()
    else:
        tenants = await repo.list_by_ids(list(access.principal.tenant_ids))
    return [TenantOut(**t.model_dump()) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("tenants", "read"))
) -> TenantOut:
    """Fetch a tenant by id.

    Args:
        tenant_id (UUID): Id of the tenant.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        TenantOut: The matching tenant.

    Raises:
        HTTPException: 404 if the tenant does not exist or is outside the
            caller's tenants (indistinguishable on purpose).
    """
    access.tenant(tenant_id)
    tenant = await request.app.state.tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return TenantOut(**tenant.model_dump())


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("tenants", "write")),
) -> TenantOut:
    """Update a tenant's fields.

    Args:
        tenant_id (UUID): Id of the tenant to update.
        body (TenantUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        TenantOut: The updated tenant.

    Raises:
        HTTPException: 404 if the tenant does not exist.
    """
    tenant = await request.app.state.tenant_repo.update(
        tenant_id, **body.model_dump(exclude_unset=True)
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return TenantOut(**tenant.model_dump())


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("tenants", "write"))
) -> None:
    """Delete a tenant.

    Args:
        tenant_id (UUID): Id of the tenant to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Raises:
        HTTPException: 404 if the tenant does not exist.
    """
    deleted = await request.app.state.tenant_repo.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="tenant not found")
