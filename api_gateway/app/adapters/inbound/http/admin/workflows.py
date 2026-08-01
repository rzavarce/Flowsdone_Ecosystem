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
    workflows = await request.app.state.workflow_config_repo.list_by_project(project_id)
    return [WorkflowConfigOut(**w.model_dump()) for w in workflows]


@router.get("/{workflow_id}", response_model=WorkflowConfigOut)
async def get_workflow(workflow_id: UUID, request: Request) -> WorkflowConfigOut:
    workflow = await request.app.state.workflow_config_repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowConfigOut(**workflow.model_dump())


@router.patch("/{workflow_id}", response_model=WorkflowConfigOut)
async def update_workflow(
    workflow_id: UUID, body: WorkflowConfigUpdate, request: Request
) -> WorkflowConfigOut:
    workflow = await request.app.state.workflow_config_repo.update(
        workflow_id, **body.model_dump(exclude_unset=True)
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    return WorkflowConfigOut(**workflow.model_dump())


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: UUID, request: Request) -> None:
    deleted = await request.app.state.workflow_config_repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="workflow not found")
