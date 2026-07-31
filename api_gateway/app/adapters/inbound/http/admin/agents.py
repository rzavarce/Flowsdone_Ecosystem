from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import require_admin_api_key
from .schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(
    prefix="/agents",
    tags=["admin:agents"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(body: AgentCreate, request: Request) -> AgentOut:
    agent = await request.app.state.agent_repo.create(
        project_id=body.project_id,
        name=body.name,
        langflow_flow_id=body.langflow_flow_id,
        config=body.config,
        is_default=body.is_default,
    )
    return AgentOut(**agent.model_dump())


@router.get("", response_model=list[AgentOut])
async def list_agents(request: Request, project_id: Optional[UUID] = None) -> list[AgentOut]:
    agents = await request.app.state.agent_repo.list_by_project(project_id)
    return [AgentOut(**a.model_dump()) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: UUID, request: Request) -> AgentOut:
    agent = await request.app.state.agent_repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut(**agent.model_dump())


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: UUID, body: AgentUpdate, request: Request) -> AgentOut:
    agent = await request.app.state.agent_repo.update(
        agent_id, **body.model_dump(exclude_unset=True)
    )
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut(**agent.model_dump())


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, request: Request) -> None:
    deleted = await request.app.state.agent_repo.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="agent not found")
