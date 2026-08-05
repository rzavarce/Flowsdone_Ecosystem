"""Admin CRUD endpoints for projects."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_admin_api_key
from .schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(
    prefix="/projects",
    tags=["admin:projects"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, request: Request) -> ProjectOut:
    """Create a project owned by a tenant.

    Args:
        body (ProjectCreate): Project fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.

    Returns:
        ProjectOut: The created project.
    """
    project = await request.app.state.project_repo.create(
        tenant_id=body.tenant_id, name=body.name, slug=body.slug
    )
    return ProjectOut(**project.model_dump())


@router.get("", response_model=list[ProjectOut])
async def list_projects(request: Request, tenant_id: Optional[UUID] = None) -> list[ProjectOut]:
    """List projects, optionally filtered by tenant.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.
        tenant_id (Optional[UUID]): If given, only return projects
            owned by this tenant.

    Returns:
        list[ProjectOut]: The matching projects.
    """
    projects = await request.app.state.project_repo.list_by_tenant(tenant_id)
    return [ProjectOut(**p.model_dump()) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, request: Request) -> ProjectOut:
    """Fetch a project by id.

    Args:
        project_id (UUID): Id of the project.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.

    Returns:
        ProjectOut: The matching project.

    Raises:
        HTTPException: 404 if the project does not exist.
    """
    project = await request.app.state.project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectOut(**project.model_dump())


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, body: ProjectUpdate, request: Request) -> ProjectOut:
    """Update a project's fields.

    Args:
        project_id (UUID): Id of the project to update.
        body (ProjectUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.

    Returns:
        ProjectOut: The updated project.

    Raises:
        HTTPException: 404 if the project does not exist.
    """
    project = await request.app.state.project_repo.update(
        project_id, **body.model_dump(exclude_unset=True)
    )
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectOut(**project.model_dump())


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request) -> None:
    """Delete a project.

    Args:
        project_id (UUID): Id of the project to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.project_repo`.

    Raises:
        HTTPException: 404 if the project does not exist.
    """
    deleted = await request.app.state.project_repo.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="project not found")
