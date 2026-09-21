"""Admin CRUD endpoints for Langflow agents.

Agents belong to a project, and projects to a tenant, so each operation is
checked against the caller's tenants. Botmasters may create and edit them, alongside admins and tenant managers.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["admin:agents"])


async def _load_scoped(request: Request, access: AdminAccess, agent_id: UUID):
    """Load a agent and require it to be inside the caller's tenants.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        access (AdminAccess): The authenticated caller.
        agent_id (UUID): Id of the agent.

    Returns:
        The agent domain object.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    item = await request.app.state.agent_repo.get_by_id(agent_id)
    if not item:
        raise HTTPException(status_code=404, detail="agent not found")
    await access.project(item.project_id, resource="agent")
    return item


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "write")),
) -> AgentOut:
    """Create an agent for a project.

    Args:
        body (AgentCreate): Fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        AgentOut: The created agent.

    Raises:
        HTTPException: 404 if the project is outside the caller's tenants.
    """
    await access.project(body.project_id)
    item = await request.app.state.agent_repo.create(
        project_id=body.project_id,
        name=body.name,
        langflow_flow_id=body.langflow_flow_id,
        config=body.config,
        is_default=body.is_default,
    )
    return AgentOut(**item.model_dump())


@router.get("", response_model=list[AgentOut])
async def list_agents(
    request: Request,
    project_id: Optional[UUID] = None,
    access: AdminAccess = Depends(admin_access("agents", "read")),
) -> list[AgentOut]:
    """List Langflow agents the caller can see, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        project_id (Optional[UUID]): If given, only return items owned by this project.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[AgentOut]: The matching items, limited to the caller's tenants.

    Raises:
        HTTPException: 404 if `project_id` is outside the caller's tenants.
    """
    items = await access.list_by_project(
        request.app.state.agent_repo.list_by_project, project_id, resource="project"
    )
    return [AgentOut(**i.model_dump()) for i in items]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "read")),
) -> AgentOut:
    """Fetch an agent by id.

    Args:
        agent_id (UUID): Id of the agent.
        request (Request): The incoming FastAPI request.
        access (AdminAccess): The authenticated caller.

    Returns:
        AgentOut: The matching agent.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    item = await _load_scoped(request, access, agent_id)
    return AgentOut(**item.model_dump())


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "write")),
) -> AgentOut:
    """Update an agent's fields.

    Args:
        agent_id (UUID): Id of the agent to update.
        body (AgentUpdate): Fields to update; unset fields are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        AgentOut: The updated agent.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    await _load_scoped(request, access, agent_id)
    item = await request.app.state.agent_repo.update(agent_id, **body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut(**item.model_dump())


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "write")),
) -> None:
    """Delete an agent.

    Args:
        agent_id (UUID): Id of the agent to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.agent_repo`.
        access (AdminAccess): The authenticated caller.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    await _load_scoped(request, access, agent_id)
    deleted = await request.app.state.agent_repo.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="agent not found")
