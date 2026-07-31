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
    data = connection.model_dump(exclude={"credentials"})
    return ChannelConnectionOut(**data, has_credentials=bool(connection.credentials))


@router.post("", response_model=ChannelConnectionOut, status_code=201)
async def create_channel_connection(
    body: ChannelConnectionCreate, request: Request
) -> ChannelConnectionOut:
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
    connections = await request.app.state.channel_connection_repo.list_by_project(project_id)
    return [_to_out(c) for c in connections]


@router.get("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def get_channel_connection(channel_connection_id: UUID, request: Request) -> ChannelConnectionOut:
    connection = await request.app.state.channel_connection_repo.get_by_id(channel_connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    return _to_out(connection)


@router.patch("/{channel_connection_id}", response_model=ChannelConnectionOut)
async def update_channel_connection(
    channel_connection_id: UUID, body: ChannelConnectionUpdate, request: Request
) -> ChannelConnectionOut:
    connection = await request.app.state.channel_connection_repo.update(
        channel_connection_id, **body.model_dump(exclude_unset=True)
    )
    if not connection:
        raise HTTPException(status_code=404, detail="channel_connection not found")
    return _to_out(connection)


@router.delete("/{channel_connection_id}", status_code=204)
async def delete_channel_connection(channel_connection_id: UUID, request: Request) -> None:
    deleted = await request.app.state.channel_connection_repo.delete(channel_connection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="channel_connection not found")
