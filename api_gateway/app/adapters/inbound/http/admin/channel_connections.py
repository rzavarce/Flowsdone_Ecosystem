"""Admin CRUD endpoints for channel connections.

A connection belongs to a project (so to a tenant) and points at the agent
that answers on it. Besides the tenant scoping, the agent must belong to the
same project: otherwise a manager could bind their channel to another
tenant's agent and divert their own messages to it. Restricted to `admin`
and `tenant_manager`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.services.webhook_registration import WebhookRegistrationError
from app.domain.models.channel_connection import ChannelConnection
from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import ChannelConnectionCreate, ChannelConnectionOut, ChannelConnectionUpdate

router = APIRouter(prefix="/channel-connections", tags=["admin:channel-connections"])


async def _load_scoped(
    request: Request, access: AdminAccess, channel_connection_id: UUID
) -> ChannelConnection:
    """Load a channel connection and require it to be inside the caller's tenants.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.
        access (AdminAccess): The authenticated caller.
        channel_connection_id (UUID): Id of the connection.

    Returns:
        ChannelConnection: The connection.

    Raises:
        HTTPException: 404 if it does not exist or is outside the caller's tenants.
    """
    connection = await request.app.state.channel_connection_repo.get_by_id(channel_connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    await access.project(connection.project_id, resource="channel_connection")
    return connection


def _to_out(connection: ChannelConnection) -> ChannelConnectionOut:
    """Convert a ChannelConnection domain object into its response
    schema, stripping raw credentials.

    Args:
        connection (ChannelConnection): The domain object to convert.

    Returns:
        ChannelConnectionOut: The response schema, without credentials.
    """
    data = connection.model_dump(exclude={"credentials"})
    return ChannelConnectionOut(**data, has_credentials=bool(connection.credentials))


@router.post("", response_model=ChannelConnectionOut, status_code=201)
async def create_channel_connection(
    body: ChannelConnectionCreate,
    request: Request,
    access: AdminAccess = Depends(admin_access("channel_connections", "write")),
) -> ChannelConnectionOut:
    """Create a channel connection for a project.

    For channels with an auto-registration flow (Telegram today), this
    also generates the webhook shared secret if not supplied and
    registers the webhook with the external platform — see
    CreateChannelConnectionUseCase.

    Args:
        body (ChannelConnectionCreate): Channel connection fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.create_channel_connection_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ChannelConnectionOut: The created channel connection.

    Raises:
        HTTPException: 404 if the project is outside the caller's tenants,
            400 if the agent does not belong to the project, 502 if the
            channel has an auto-registration flow and the external platform
            rejected it.
    """
    await access.project(body.project_id)
    await access.agent_in_project(body.agent_id, body.project_id)
    try:
        connection = await request.app.state.create_channel_connection_use_case.execute(
            project_id=body.project_id,
            agent_id=body.agent_id,
            channel_type=body.channel_type,
            external_id=body.external_id,
            display_name=body.display_name,
            credentials=body.credentials,
            config=body.config,
        )
    except WebhookRegistrationError as exc:
        raise HTTPException(status_code=502, detail=f"webhook registration failed: {exc}") from exc
    return _to_out(connection)


@router.get("", response_model=list[ChannelConnectionOut])
async def list_channel_connections(
    request: Request,
    project_id: Optional[UUID] = None,
    access: AdminAccess = Depends(admin_access("channel_connections", "read")),
) -> list[ChannelConnectionOut]:
    """List channel connections, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.
        project_id (Optional[UUID]): If given, only return connections
            owned by this project.
        access (AdminAccess): The authenticated caller.

    Returns:
        list[ChannelConnectionOut]: The matching channel connections,
        limited to the caller's tenants.

    Raises:
        HTTPException: 404 if `project_id` is outside the caller's tenants.
    """
    connections = await access.list_by_project(
        request.app.state.channel_connection_repo.list_by_project, project_id, resource="project"
    )
    return [_to_out(c) for c in connections]


@router.get("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def get_channel_connection(
    channel_connection_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("channel_connections", "read")),
) -> ChannelConnectionOut:
    """Fetch a channel connection by id.

    Args:
        channel_connection_id (UUID): Id of the channel connection.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ChannelConnectionOut: The matching channel connection.

    Raises:
        HTTPException: 404 if the channel connection does not exist or is
            outside the caller's tenants.
    """
    connection = await _load_scoped(request, access, channel_connection_id)
    return _to_out(connection)


@router.patch("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def update_channel_connection(
    channel_connection_id: UUID,
    body: ChannelConnectionUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("channel_connections", "write")),
) -> ChannelConnectionOut:
    """Update a channel connection's fields.

    For channels with an auto-registration flow (Telegram today), a
    `credentials` update also re-registers the webhook with the
    external platform, preserving the existing secret unless the
    caller explicitly overrides it — see UpdateChannelConnectionUseCase.

    Args:
        channel_connection_id (UUID): Id of the connection to update.
        body (ChannelConnectionUpdate): Fields to update; unset fields
            are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.update_channel_connection_use_case`.
        access (AdminAccess): The authenticated caller.

    Returns:
        ChannelConnectionOut: The updated channel connection.

    Raises:
        HTTPException: 404 if the channel connection does not exist or is
            outside the caller's tenants, 400 if a new `agent_id` does not
            belong to the connection's project, 502 if the channel has an
            auto-registration flow and the external platform rejected the
            new registration.
    """
    existing = await _load_scoped(request, access, channel_connection_id)
    if body.agent_id is not None:
        await access.agent_in_project(body.agent_id, existing.project_id)
    try:
        connection = await request.app.state.update_channel_connection_use_case.execute(
            channel_connection_id, **body.model_dump(exclude_unset=True)
        )
    except WebhookRegistrationError as exc:
        raise HTTPException(status_code=502, detail=f"webhook registration failed: {exc}") from exc
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    return _to_out(connection)


@router.delete("/{channel_connection_id}", status_code=204)
async def delete_channel_connection(
    channel_connection_id: UUID,
    request: Request,
    access: AdminAccess = Depends(admin_access("channel_connections", "write")),
) -> None:
    """Delete a channel connection.

    For channels with an auto-registration flow (Telegram today), this
    also deregisters the webhook from the external platform on a
    best-effort basis — see DeleteChannelConnectionUseCase.

    Args:
        channel_connection_id (UUID): Id of the connection to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.delete_channel_connection_use_case`.
        access (AdminAccess): The authenticated caller.

    Raises:
        HTTPException: 404 if the channel connection does not exist or is
            outside the caller's tenants.
    """
    await _load_scoped(request, access, channel_connection_id)
    deleted = await request.app.state.delete_channel_connection_use_case.execute(
        channel_connection_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="channel_connection not found")
