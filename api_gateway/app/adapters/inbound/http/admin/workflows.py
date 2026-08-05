"""Admin CRUD endpoints for n8n workflow configurations."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_admin_api_key
from .schemas import WorkflowConfigCreate, WorkflowConfigOut, WorkflowConfigUpdate

router = APIRouter(
    prefix="/workflows",
    tags=["admin:workflows"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=WorkflowConfigOut, status_code=201)
async def create_workflow(body: WorkflowConfigCreate, request: Request) -> WorkflowConfigOut:
    """Create an n8n workflow trigger configuration for a project.

    Args:
        body (WorkflowConfigCreate): Workflow configuration fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.

    Returns:
        WorkflowConfigOut: The created workflow configuration.
    """
    workflow = await request.app.state.workflow_config_repo.create(
        project_id=body.project_id,
        name=body.name,
        n8n_workflow_id=body.n8n_workflow_id,
        trigger_type=body.trigger_type,
        config=body.config,
    )
    return WorkflowConfigOut(**workflow.model_dump())


@router.get("", response_model=list[WorkflowConfigOut])
async def list_workflows(request: Request, project_id: Optional[UUID] = None) -> list[WorkflowConfigOut]:
    """List workflow configurations, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.
        project_id (Optional[UUID]): If given, only return configs
            owned by this project.

    Returns:
        list[WorkflowConfigOut]: The matching workflow configurations.
    """
    workflows = await request.app.state.workflow_config_repo.list_by_project(project_id)
    return [WorkflowConfigOut(**w.model_dump()) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowConfigOut)
async def get_workflow(workflow_id: UUID, request: Request) -> WorkflowConfigOut:
    """Fetch a workflow configuration by id.

    Args:
        workflow_id (UUID): Id of the workflow configuration.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.

    Returns:
        WorkflowConfigOut: The matching workflow configuration.

    Raises:
        HTTPException: 404 if the workflow configuration does not exist.
    """
    workflow = await request.app.state.workflow_config_repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowConfigOut(**workflow.model_dump())


@router.patch("/{workflow_id}", response_model=WorkflowConfigOut)
async def update_workflow(
    workflow_id: UUID, body: WorkflowConfigUpdate, request: Request
) -> WorkflowConfigOut:
    """Update a workflow configuration's fields.

    Args:
        workflow_id (UUID): Id of the workflow configuration to update.
        body (WorkflowConfigUpdate): Fields to update; unset fields are
            left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.

    Returns:
        WorkflowConfigOut: The updated workflow configuration.

    Raises:
        HTTPException: 404 if the workflow configuration does not exist.
    """
    workflow = await request.app.state.workflow_config_repo.update(
        workflow_id, **body.model_dump(exclude_unset=True)
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowConfigOut(**workflow.model_dump())


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: UUID, request: Request) -> None:
    """Delete a workflow configuration.

    Args:
        workflow_id (UUID): Id of the workflow configuration to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.workflow_config_repo`.

    Raises:
        HTTPException: 404 if the workflow configuration does not exist.
    """
    deleted = await request.app.state.workflow_config_repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="workflow not found")
