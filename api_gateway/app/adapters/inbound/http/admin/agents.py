"""Admin CRUD endpoints for Langflow agents."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.auth import require_admin_api_key
from app.adapters.inbound.http.admin.schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(
    prefix="/agents",
    tags=["admin:agents"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(body: AgentCreate, request: Request) -> AgentOut:
    """Create a Langflow agent for a project.

    Args:
        body (AgentCreate): Agent fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.

    Returns:
        AgentOut: The created agent.
    """
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
    """List agents, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        project_id (Optional[UUID]): If given, only return agents
            owned by this project.

    Returns:
        list[AgentOut]: The matching agents.
    """
    agents = await request.app.state.agent_repo.list_by_project(project_id)
    return [AgentOut(**a.model_dump()) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: UUID, request: Request) -> AgentOut:
    """Fetch an agent by id.

    Args:
        agent_id (UUID): Id of the agent.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.

    Returns:
        AgentOut: The matching agent.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    agent = await request.app.state.agent_repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut(**agent.model_dump())


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: UUID, body: AgentUpdate, request: Request) -> AgentOut:
    """Update an agent's fields.

    Args:
        agent_id (UUID): Id of the agent to update.
        body (AgentUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.

    Returns:
        AgentOut: The updated agent.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    agent = await request.app.state.agent_repo.update(
        agent_id, **body.model_dump(exclude_unset=True)
    )
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut(**agent.model_dump())


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: UUID, request: Request) -> None:
    """Delete an agent.

    Args:
        agent_id (UUID): Id of the agent to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.

    Raises:
        HTTPException: 404 if the agent does not exist.
    """
    deleted = await request.app.state.agent_repo.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="agent not found")
