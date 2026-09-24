"""Admin CRUD endpoints for projects.

Every project belongs to a tenant, so each operation is checked against the
caller's tenants. Writing is limited to `admin` and `tenant_manager`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError
from app.domain.ports.outbound import LangflowSessionError

router = APIRouter(prefix="/projects", tags=["admin:projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("projects", "write")),
) -> ProjectOut:
    """Create a project owned by a tenant.

    Args:
        body (ProjectCreate): Project fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ProjectOut: The created project.

    Raises:
        HTTPException: 404 if the tenant is outside the caller's tenants.
    """
    access.tenant(body.tenant_id)
    project = await request.app.state.project_repo.create(
        tenant_id=body.tenant_id, name=body.name, slug=body.slug
    )
    return ProjectOut(**project.model_dump())


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    request: Request,
    tenant_id: Optional[UUID] = None,
    access: AdminAccess = Depends(admin_access("projects", "read")),
) -> list[ProjectOut]:
    """List the projects the caller can see, optionally filtered by tenant.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.
        tenant_id (Optional[UUID]): If given, only return projects owned by
            this tenant.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[ProjectOut]: The matching projects, limited to the caller's tenants.

    Raises:
        HTTPException: 404 if `tenant_id` is outside the caller's tenants.
    """
    if tenant_id is not None:
        access.tenant(tenant_id)
        projects = await request.app.state.project_repo.list_by_tenant(tenant_id)
    else:
        projects = await access.visible_projects()
    return [ProjectOut(**p.model_dump()) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("projects", "read")),
) -> ProjectOut:
    """Fetch a project by id.

    Args:
        project_id (UUID): Id of the project.
        request (Request): The incoming FastAPI request.
        access (AdminAccess): The authenticated caller.

    Returns:
        ProjectOut: The matching project.

    Raises:
        HTTPException: 404 if the project does not exist or is outside the
            caller's tenants.
    """
    project = await access.project(project_id)
    return ProjectOut(**project.model_dump())


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("projects", "write")),
) -> ProjectOut:
    """Update a project's fields.

    Args:
        project_id (UUID): Id of the project to update.
        body (ProjectUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ProjectOut: The updated project.

    Raises:
        HTTPException: 404 if the project does not exist or is outside the
            caller's tenants.
    """
    await access.project(project_id)
    project = await request.app.state.project_repo.update(
        project_id, **body.model_dump(exclude_unset=True)
    )
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectOut(**project.model_dump())


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("projects", "write")),
) -> None:
    """Delete a project.

    Its Langflow folder (and the flows in it) is deleted first; if Langflow
    fails, the project is kept.

    Args:
        project_id (UUID): Id of the project to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.delete_project_use_case`.
        access (AdminAccess): The authenticated caller.

    Raises:
        HTTPException: 404 if the project does not exist or is outside the
            caller's tenants; 502 if Langflow fails.
    """
    await access.project(project_id)
    try:
        deleted = await request.app.state.delete_project_use_case.execute(project_id)
    except (LangflowSessionError, LangflowTargetNotFoundError) as exc:
        raise HTTPException(status_code=502, detail=f"langflow unavailable: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="project not found")
