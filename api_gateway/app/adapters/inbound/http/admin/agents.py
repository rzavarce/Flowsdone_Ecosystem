"""Admin CRUD endpoints for Langflow agents.

Agents belong to a project, and projects to a tenant, so each operation is
checked against the caller's tenants. Botmasters may create and edit them, alongside admins and tenant managers.

The rules live in `ManageAgentsUseCase`: for console users the flow must be
in the project's Langflow folder (machine callers - API key, the internal
onboarding agent - may register any flow id, as before); one default agent
per project; an agent with channels cannot be deleted (409).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import AgentCreate, AgentOut, AgentUpdate, BaseAgentCreate
from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError
from app.application.use_cases.manage_agents import AgentInUseError, FlowNotInProjectError
from app.domain.ports.outbound import LangflowSessionError

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


def _verify_flow(access: AdminAccess) -> bool:
    """Whether the flow must be checked against the project's Langflow folder.

    Args:
        access (AdminAccess): The caller.

    Returns:
        bool: True for console users; False for the admin API key (scripts,
        the onboarding agent), which may register flows living anywhere.
    """
    return access.principal.user_id is not None


def _flow_errors(exc: Exception) -> HTTPException:
    """Map flow verification errors to HTTP.

    Args:
        exc (Exception): FlowNotInProjectError or LangflowSessionError.

    Returns:
        HTTPException: 400 or 502.
    """
    if isinstance(exc, FlowNotInProjectError):
        return HTTPException(status_code=400, detail="flow not found in the project's Langflow folder")
    return HTTPException(status_code=502, detail=f"langflow unavailable: {exc}")


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
        HTTPException: 404 if the project is outside the caller's tenants;
            400 if the flow is not in the project's Langflow folder; 409 if
            the name is taken in the project; 502 if Langflow fails.
    """
    await access.project(body.project_id)
    try:
        item = await request.app.state.manage_agents_use_case.create(
            project_id=body.project_id,
            name=body.name,
            langflow_flow_id=body.langflow_flow_id,
            config=body.config,
            is_default=body.is_default,
            verify_flow=_verify_flow(access),
        )
    except (FlowNotInProjectError, LangflowSessionError) as exc:
        raise _flow_errors(exc) from exc
    return AgentOut(**item.model_dump())


@router.post("/base", response_model=AgentOut, status_code=201)
async def create_base_agent(
    body: BaseAgentCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "write")),
) -> AgentOut:
    """Create a project's base agent (new-client wizard): a chat flow with
    conversation memory and a prompt built from the answers, created in
    the project's Langflow folder and registered as its default agent. Its
    OpenAI component is created WITHOUT an API key: it is set by hand in the
    editor for each client (the onboarding checklist flags it until then).

    Args:
        body (BaseAgentCreate): Project and the assistant's answers.
        request (Request): Used to reach `request.app.state.create_base_agent_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        AgentOut: The new agent.

    Raises:
        HTTPException: 404 if the project is outside the caller's tenants;
            409 if the project already has an agent with that name; 502 if
            Langflow fails.
    """
    await access.project(body.project_id)
    try:
        item = await request.app.state.create_base_agent_use_case.execute(
            project_id=body.project_id,
            assistant_name=body.assistant_name.strip(),
            tone=body.tone,
            instructions=body.instructions,
        )
    except LangflowTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LangflowSessionError as exc:
        raise HTTPException(status_code=502, detail=f"langflow unavailable: {exc}") from exc
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
        HTTPException: 404 if it does not exist or is outside the caller's
            tenants; 400 if a new flow is not in the project's Langflow
            folder; 409 if the new name is taken; 502 if Langflow fails.
    """
    agent = await _load_scoped(request, access, agent_id)
    try:
        item = await request.app.state.manage_agents_use_case.update(
            agent, verify_flow=_verify_flow(access), **body.model_dump(exclude_unset=True)
        )
    except (FlowNotInProjectError, LangflowSessionError) as exc:
        raise _flow_errors(exc) from exc
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
        HTTPException: 404 if it does not exist or is outside the caller's
            tenants; 409 if channels are still connected to it.
    """
    agent = await _load_scoped(request, access, agent_id)
    try:
        deleted = await request.app.state.manage_agents_use_case.delete(agent)
    except AgentInUseError as exc:
        raise HTTPException(status_code=409, detail="agent has channels") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="agent not found")
