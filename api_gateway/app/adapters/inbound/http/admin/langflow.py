"""Admin endpoint that opens the embedded Langflow as a tenant's user.

Restricted to platform staff (`admin`): see the `langflow` entry of
`access_control.POLICY`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from urllib.parse import quote

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import LangflowSessionCreate, LangflowSessionOut
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
