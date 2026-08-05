"""Admin CRUD endpoints for channel connections."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from .....domain.models.channel_connection import ChannelConnection
from .auth import require_admin_api_key
from .schemas import ChannelConnectionCreate, ChannelConnectionOut, ChannelConnectionUpdate

router = APIRouter(
    prefix="/channel-connections",
    tags=["admin:channel-connections"],
    dependencies=[Depends(require_admin_api_key)],
)


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
    body: ChannelConnectionCreate, request: Request
) -> ChannelConnectionOut:
    """Create a channel connection for a project.

    Args:
        body (ChannelConnectionCreate): Channel connection fields to create.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.

    Returns:
        ChannelConnectionOut: The created channel connection.
    """
    connection = await request.app.state.channel_connection_repo.create(
        project_id=body.project_id,
        agent_id=body.agent_id,
        channel_type=body.channel_type,
        external_id=body.external_id,
        display_name=body.display_name,
        credentials=body.credentials,
        config=body.config,
    )
    return _to_out(connection)


@router.get("", response_model=list[ChannelConnectionOut])
async def list_channel_connections(
    request: Request, project_id: Optional[UUID] = None
) -> list[ChannelConnectionOut]:
    """List channel connections, optionally filtered by project.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.
        project_id (Optional[UUID]): If given, only return connections
            owned by this project.

    Returns:
        list[ChannelConnectionOut]: The matching channel connections.
    """
    connections = await request.app.state.channel_connection_repo.list_by_project(project_id)
    return [_to_out(c) for c in connections]


@router.get("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def get_channel_connection(channel_connection_id: UUID, request: Request) -> ChannelConnectionOut:
    """Fetch a channel connection by id.

    Args:
        channel_connection_id (UUID): Id of the channel connection.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.

    Returns:
        ChannelConnectionOut: The matching channel connection.

    Raises:
        HTTPException: 404 if the channel connection does not exist.
    """
    connection = await request.app.state.channel_connection_repo.get_by_id(channel_connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    return _to_out(connection)


@router.patch("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def update_channel_connection(
    channel_connection_id: UUID, body: ChannelConnectionUpdate, request: Request
) -> ChannelConnectionOut:
    """Update a channel connection's fields.

    Args:
        channel_connection_id (UUID): Id of the connection to update.
        body (ChannelConnectionUpdate): Fields to update; unset fields
            are left unchanged.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.

    Returns:
        ChannelConnectionOut: The updated channel connection.

    Raises:
        HTTPException: 404 if the channel connection does not exist.
    """
    connection = await request.app.state.channel_connection_repo.update(
        channel_connection_id, **body.model_dump(exclude_unset=True)
    )
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    return _to_out(connection)


@router.delete("/{channel_connection_id}", status_code=204)
async def delete_channel_connection(channel_connection_id: UUID, request: Request) -> None:
    """Delete a channel connection.

    Args:
        channel_connection_id (UUID): Id of the connection to delete.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_connection_repo`.

    Raises:
        HTTPException: 404 if the channel connection does not exist.
    """
    deleted = await request.app.state.channel_connection_repo.delete(channel_connection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="channel_connection not found")
