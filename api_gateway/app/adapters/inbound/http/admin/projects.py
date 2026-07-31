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
    project = await request.app.state.project_repo.create(
        tenant_id=body.tenant_id, name=body.name, slug=body.slug
    )
    return ProjectOut(**project.model_dump())


@router.get("", response_model=list[ProjectOut])
async def list_projects(request: Request, tenant_id: Optional[UUID] = None) -> list[ProjectOut]:
    projects = await request.app.state.project_repo.list_by_tenant(tenant_id)
    return [ProjectOut(**p.model_dump()) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, request: Request) -> ProjectOut:
    project = await request.app.state.project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectOut(**project.model_dump())


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, body: ProjectUpdate, request: Request) -> ProjectOut:
    project = await request.app.state.project_repo.update(
        project_id, **body.model_dump(exclude_unset=True)
    )
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectOut(**project.model_dump())


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request) -> None:
    deleted = await request.app.state.project_repo.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="project not found")
