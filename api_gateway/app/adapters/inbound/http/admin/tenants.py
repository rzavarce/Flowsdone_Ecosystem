"""Admin CRUD endpoints for tenants."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_admin_api_key
from .schemas import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(
    prefix="/tenants",
    tags=["admin:tenants"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=TenantOut, status_code=201)
async def create_tenant(body: TenantCreate, request: Request) -> TenantOut:
    """Create a tenant.

    Args:
        body (TenantCreate): Tenant fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.

    Returns:
        TenantOut: The created tenant.
    """
    tenant = await request.app.state.tenant_repo.create(name=body.name, slug=body.slug)
    return TenantOut(**tenant.model_dump())


@router.get("", response_model=list[TenantOut])
async def list_tenants(request: Request) -> list[TenantOut]:
    """List all tenants.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.

    Returns:
        list[TenantOut]: All existing tenants.
    """
    tenants = await request.app.state.tenant_repo.list()
    return [TenantOut(**t.model_dump()) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: UUID, request: Request) -> TenantOut:
    """Fetch a tenant by id.

    Args:
        tenant_id (UUID): Id of the tenant.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.

    Returns:
        TenantOut: The matching tenant.

    Raises:
        HTTPException: 404 if the tenant does not exist.
    """
    tenant = await request.app.state.tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return TenantOut(**tenant.model_dump())


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: UUID, body: TenantUpdate, request: Request) -> TenantOut:
    """Update a tenant's fields.

    Args:
        tenant_id (UUID): Id of the tenant to update.
        body (TenantUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.

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
async def delete_tenant(tenant_id: UUID, request: Request) -> None:
    """Delete a tenant.

    Args:
        tenant_id (UUID): Id of the tenant to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.tenant_repo`.

    Raises:
        HTTPException: 404 if the tenant does not exist.
    """
    deleted = await request.app.state.tenant_repo.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="tenant not found")
