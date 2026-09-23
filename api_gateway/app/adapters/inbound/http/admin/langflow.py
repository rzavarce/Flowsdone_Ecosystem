"""Admin endpoints for the embedded Langflow: open it as a tenant's user,
and list the flows of a project's folder (to register them as agents).

Restricted to platform staff: see the `langflow` and `agents` entries of
`access_control.POLICY`.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from urllib.parse import quote

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import LangflowFlowOut, LangflowSessionCreate, LangflowSessionOut
from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError
from app.core.config import settings
from app.domain.ports.outbound import LangflowSessionError

router = APIRouter(prefix="/langflow", tags=["admin:langflow"])


@router.post("/session", response_model=LangflowSessionOut)
async def create_langflow_session(
    body: LangflowSessionCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("langflow", "write")),
) -> LangflowSessionOut:
    """Provision the tenant's Langflow user/folders and return the SSO URL.

    Args:
        body (LangflowSessionCreate): Tenant (and optionally project) to open.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.prepare_langflow_session_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        LangflowSessionOut: The gateway URL to load in the iframe.

    Raises:
        HTTPException: 404 if the tenant or project is outside the caller's
            scope or does not exist; 502 if Langflow fails.
    """
    access.tenant(body.tenant_id)
    if body.project_id is not None:
        await access.project(body.project_id)
    try:
        ticket = await request.app.state.prepare_langflow_session_use_case.execute(
            body.tenant_id, body.project_id
        )
    except LangflowTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LangflowSessionError as exc:
        raise HTTPException(status_code=502, detail=f"langflow unavailable: {exc}") from exc
    return LangflowSessionOut(url=f"{settings.LANGFLOW_SSO_BASE_URL}/langflow-sso?ticket={quote(ticket)}")


@router.get("/flows", response_model=list[LangflowFlowOut])
async def list_project_flows(
    project_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("agents", "read")),
) -> list[LangflowFlowOut]:
    """Flows in a project's Langflow folder, each with the agent already
    registered for it (if any). Provisions the tenant's Langflow user and
    folders if needed, like opening the editor.

    Args:
        project_id (UUID): The project.
        request (Request): Used to reach `request.app.state.list_project_flows_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[LangflowFlowOut]: The flows, by name.

    Raises:
        HTTPException: 404 if the project is outside the caller's scope or
            does not exist; 502 if Langflow fails.
    """
    await access.project(project_id)
    try:
        flows = await request.app.state.list_project_flows_use_case.execute(project_id)
    except LangflowTargetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LangflowSessionError as exc:
        raise HTTPException(status_code=502, detail=f"langflow unavailable: {exc}") from exc
    return [LangflowFlowOut(**vars(f)) for f in flows]

