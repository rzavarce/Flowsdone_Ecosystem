"""Admin endpoints for CRM integrations (one per project) and for handing
a conversation over to the CRM by hand. Managers set up their tenants'
integrations; any staff member can read them. Secrets are returned only
when created or rotated.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import (
    CrmHandoffCreate,
    CrmHandoffOut,
    CrmIntegrationCreate,
    CrmIntegrationOut,
    CrmIntegrationSecretsOut,
    CrmIntegrationTestOut,
    CrmIntegrationUpdate,
)
from app.application.use_cases.crm_handoff import HandoffNotPossibleError
from app.application.use_cases.crm_integrations import InvalidCrmIntegrationError
from app.core.config import settings
from app.domain.models.crm import CrmIntegration

router = APIRouter(tags=["admin:crm"])


def _out(integration: CrmIntegration) -> CrmIntegrationOut:
    """Response view of an integration, without secrets.

    Args:
        integration (CrmIntegration): The integration.

    Returns:
        CrmIntegrationOut: The view, with the URLs the CRM calls back.
    """
    api = f"{settings.PUBLIC_BASE_URL}/integrations/crm/{integration.id}"
    return CrmIntegrationOut(
        **integration.model_dump(exclude={"credentials"}), reply_url=f"{api}/messages", close_url=f"{api}/close"
    )


def _with_secrets(integration: CrmIntegration) -> CrmIntegrationSecretsOut:
    """Response view of an integration including its secrets.

    Args:
        integration (CrmIntegration): The integration.

    Returns:
        CrmIntegrationSecretsOut: The view with signing_secret and api_key.
    """
    return CrmIntegrationSecretsOut(
        **_out(integration).model_dump(),
        signing_secret=integration.credentials.get("signing_secret", ""),
        api_key=integration.credentials.get("api_key", ""),
    )


async def _load(request: Request, access: AdminAccess, integration_id: UUID) -> CrmIntegration:
    """Load an integration inside the caller's tenants.

    Args:
        request (Request): The request (reaches app.state).
        access (AdminAccess): The caller.
        integration_id (UUID): Integration id.

    Returns:
        CrmIntegration: The integration.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    integration = await request.app.state.crm_integration_repo.get(integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="crm_integration not found")
    await access.project(integration.project_id, resource="crm_integration")
    return integration


@router.get("/crm-integrations", response_model=list[CrmIntegrationOut])
async def list_crm_integrations(
    request: Request,
    project_id: Optional[UUID] = None,
    access: AdminAccess = Depends(admin_access("crm_integrations", "read")),
) -> list[CrmIntegrationOut]:
    """List the CRM integrations of the caller's tenants.

    Args:
        request (Request): The request.
        project_id (Optional[UUID]): Only this project's.
        access (AdminAccess): The caller.

    Returns:
        list[CrmIntegrationOut]: The integrations.

    Raises:
        HTTPException: 404 if `project_id` is outside the caller's tenants.
    """
    if project_id is not None:
        await access.project(project_id)
        integration = await request.app.state.crm_integration_repo.get_for_project(project_id)
        return [_out(integration)] if integration else []
    tenant_ids = None if access.unrestricted else [p.tenant_id for p in await access.visible_projects()]
    return [_out(i) for i in await request.app.state.crm_integration_repo.list(tenant_ids=tenant_ids)]


@router.post("/crm-integrations", response_model=CrmIntegrationSecretsOut, status_code=201)
async def create_crm_integration(
    body: CrmIntegrationCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> CrmIntegrationSecretsOut:
    """Create a project's CRM integration (its secrets are shown only now).

    Args:
        body (CrmIntegrationCreate): Project, provider and settings.
        request (Request): The request.
        access (AdminAccess): The caller.

    Returns:
        CrmIntegrationSecretsOut: The integration with its secrets.

    Raises:
        HTTPException: 404 if the project is outside the caller's tenants,
            400 if the settings are not usable, 409 if the project already
            has an integration.
    """
    project = await access.project(body.project_id)
    try:
        integration = await request.app.state.manage_crm_integrations_use_case.create(
            tenant_id=project.tenant_id, project_id=project.id, provider=body.provider, config=body.config
        )
    except InvalidCrmIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _with_secrets(integration)


@router.patch("/crm-integrations/{integration_id}", response_model=CrmIntegrationOut)
async def update_crm_integration(
    integration_id: UUID,
    body: CrmIntegrationUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> CrmIntegrationOut:
    """Change an integration's settings or status.

    Args:
        integration_id (UUID): Integration id.
        body (CrmIntegrationUpdate): What to change.
        request (Request): The request.
        access (AdminAccess): The caller.

    Returns:
        CrmIntegrationOut: The updated integration.

    Raises:
        HTTPException: 404 if not found, 400 if the settings are not usable.
    """
    integration = await _load(request, access, integration_id)
    try:
        updated = await request.app.state.manage_crm_integrations_use_case.update(
            integration, config=body.config, status=body.status
        )
    except InvalidCrmIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _out(updated)


@router.post("/crm-integrations/{integration_id}/rotate-secrets", response_model=CrmIntegrationSecretsOut)
async def rotate_crm_integration_secrets(
    integration_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> CrmIntegrationSecretsOut:
    """Replace the integration's secrets (the old ones stop working).

    Args:
        integration_id (UUID): Integration id.
        request (Request): The request.
        access (AdminAccess): The caller.

    Returns:
        CrmIntegrationSecretsOut: The integration with its new secrets.

    Raises:
        HTTPException: 404 if not found.
    """
    integration = await _load(request, access, integration_id)
    rotated = await request.app.state.manage_crm_integrations_use_case.rotate_secrets(integration)
    return _with_secrets(rotated)


@router.post("/crm-integrations/{integration_id}/test", response_model=CrmIntegrationTestOut)
async def test_crm_integration(
    integration_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> CrmIntegrationTestOut:
    """Send an "integration.test" event to the CRM right away.

    Args:
        integration_id (UUID): Integration id.
        request (Request): The request.
        access (AdminAccess): The caller.

    Returns:
        CrmIntegrationTestOut: Whether the CRM accepted it.

    Raises:
        HTTPException: 404 if not found.
    """
    integration = await _load(request, access, integration_id)
    error = await request.app.state.manage_crm_integrations_use_case.send_test(integration)
    return CrmIntegrationTestOut(ok=error is None, error=error)


@router.delete("/crm-integrations/{integration_id}", status_code=204)
async def delete_crm_integration(
    integration_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> None:
    """Delete an integration (past handoffs keep their history).

    Args:
        integration_id (UUID): Integration id.
        request (Request): The request.
        access (AdminAccess): The caller.

    Raises:
        HTTPException: 404 if not found.
    """
    await _load(request, access, integration_id)
    await request.app.state.crm_integration_repo.delete(integration_id)


async def _session_id_of(request: Request, conversation_id: str) -> str:
    """The switchboard session id behind a conversation reference.

    Langflow only knows the conversation's UUID (its session_id); the
    console and the CRM use the switchboard session id. Both are accepted.

    Args:
        request (Request): The request (reaches app.state).
        conversation_id (str): A session id, or a conversation UUID.

    Returns:
        str: The session id.
    """
    try:
        conversation_uuid = UUID(conversation_id)
    except ValueError:
        return conversation_id
    conversation = await request.app.state.conversation_repo.get(conversation_uuid)
    return conversation.session_id if conversation else conversation_id


@router.post("/crm-handoffs", response_model=CrmHandoffOut, status_code=201)
async def start_crm_handoff(
    body: CrmHandoffCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("crm_integrations", "write")),
) -> CrmHandoffOut:
    """Hand a live conversation over to its project's CRM.

    Args:
        body (CrmHandoffCreate): The conversation (session id, or the
            conversation UUID Langflow knows) and the reason.
        request (Request): The request.
        access (AdminAccess): The caller.

    Returns:
        CrmHandoffOut: The open handoff.

    Raises:
        HTTPException: 404 if the conversation is not live or outside the
            caller's tenants, 409 if its project has no active integration.
    """
    session_id = await _session_id_of(request, body.conversation_id)
    session = await request.app.state.session_repo.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation not found or no longer live")
    await access.project(session.project_id, resource="conversation")
    try:
        handoff = await request.app.state.start_handoff_use_case.execute(
            session_id=session_id, reason=body.reason
        )
    except HandoffNotPossibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CrmHandoffOut(
        id=handoff.id,
        conversation_id=handoff.session_id,
        integration_id=handoff.integration_id,
        status=handoff.status,
        opened_at=handoff.opened_at,
    )
