"""Admin CRUD endpoints for n8n workflow configurations.

Workflow configurations belong to a project, and projects to a tenant, so each operation is
checked against the caller's tenants. Writing is limited to `admin` and `tenant_manager`; botmasters can only read.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import WorkflowConfigCreate, WorkflowConfigOut, WorkflowConfigUpdate

router = APIRouter(prefix="/workflows", tags=["admin:workflows"])


async def _load_scoped(request: Request, access: AdminAccess, workflow_id: UUID):
    """Load a workflow and require it to be inside the caller's tenants.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        access (AdminAccess): The authenticated caller.
        workflow_id (UUID): Id of the workflow.

    Returns:
        The workflow domain object.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    item = await request.app.state.workflow_config_repo.get_by_id(workflow_id)
    if not item:
        raise HTTPException(status_code=404, detail="workflow not found")
    await access.project(item.project_id, resource="workflow")
    return item


@router.post("", response_model=WorkflowConfigOut, status_code=201)
async def create_workflow(
    body: WorkflowConfigCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("workflows", "write")),
) -> WorkflowConfigOut:
    """Create a workflow configuration for a project.

    Args:
        body (WorkflowConfigCreate): Fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        WorkflowConfigOut: The created workflow.

    Raises:
        HTTPException: 404 if the project is outside the caller's tenants.
    """
    await access.project(body.project_id)
    item = await request.app.state.workflow_config_repo.create(
        project_id=body.project_id,
        name=body.name,
        n8n_workflow_id=body.n8n_workflow_id,
        trigger_type=body.trigger_type,
        config=body.config,
    )
    return WorkflowConfigOut(**item.model_dump())


@router.get("", response_model=list[WorkflowConfigOut])
async def list_workflows(
    request: Request,
    project_id: Optional[UUID] = None,
    access: AdminAccess = Depends(admin_access("workflows", "read")),
) -> list[WorkflowConfigOut]:
    """List n8n workflow configurations the caller can see, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        project_id (Optional[UUID]): If given, only return items owned by this project.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[WorkflowConfigOut]: The matching items, limited to the caller's tenants.

    Raises:
        HTTPException: 404 if `project_id` is outside the caller's tenants.
    """
    items = await access.list_by_project(
        request.app.state.workflow_config_repo.list_by_project, project_id, resource="project"
    )
    return [WorkflowConfigOut(**i.model_dump()) for i in items]


@router.get("/{workflow_id}", response_model=WorkflowConfigOut)
async def get_workflow(
    workflow_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("workflows", "read")),
) -> WorkflowConfigOut:
    """Fetch a workflow configuration by id.

    Args:
        workflow_id (UUID): Id of the workflow.
        request (Request): The incoming FastAPI request.
        access (AdminAccess): The authenticated caller.

    Returns:
        WorkflowConfigOut: The matching workflow.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    item = await _load_scoped(request, access, workflow_id)
    return WorkflowConfigOut(**item.model_dump())


@router.patch("/{workflow_id}", response_model=WorkflowConfigOut)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowConfigUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("workflows", "write")),
) -> WorkflowConfigOut:
    """Update a workflow configuration's fields.

    Args:
        workflow_id (UUID): Id of the workflow to update.
        body (WorkflowConfigUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        WorkflowConfigOut: The updated workflow.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    await _load_scoped(request, access, workflow_id)
    item = await request.app.state.workflow_config_repo.update(workflow_id, **body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowConfigOut(**item.model_dump())


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("workflows", "write")),
) -> None:
    """Delete a workflow configuration.

    Args:
        workflow_id (UUID): Id of the workflow to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        access (AdminAccess): The authenticated caller.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    await _load_scoped(request, access, workflow_id)
    deleted = await request.app.state.workflow_config_repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="workflow not found")
