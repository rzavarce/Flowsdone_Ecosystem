from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .....domain.models.channel_app import ChannelApp, ChannelAppProvider
from .auth import require_admin_api_key
from .schemas import ChannelAppOut, ChannelAppUpsert

router = APIRouter(
    prefix="/channel-apps",
    tags=["admin:channel-apps"],
    dependencies=[Depends(require_admin_api_key)],
)


def _to_out(channel_app: ChannelApp) -> ChannelAppOut:
    data = channel_app.model_dump(exclude={"credentials"})
    return ChannelAppOut(**data, has_credentials=bool(channel_app.credentials))


@router.get("", response_model=list[ChannelAppOut])
async def list_channel_apps(request: Request) -> list[ChannelAppOut]:
    channel_apps = await request.app.state.channel_app_repo.list()
    return [_to_out(a) for a in channel_apps]


@router.get("/{provider}", response_model=ChannelAppOut)
async def get_channel_app(provider: ChannelAppProvider, request: Request) -> ChannelAppOut:
    channel_app = await request.app.state.channel_app_repo.get_by_provider(provider)
    if not channel_app:
        raise HTTPException(status_code=404, detail="channel_app not found")
    return _to_out(channel_app)


@router.put("/{provider}", response_model=ChannelAppOut)
async def upsert_channel_app(
    provider: ChannelAppProvider, body: ChannelAppUpsert, request: Request
) -> ChannelAppOut:
    channel_app = await request.app.state.channel_app_repo.upsert(
        provider=provider, credentials=body.credentials, config=body.config
    )
    return _to_out(channel_app)


@router.delete("/{provider}", status_code=204)
async def delete_channel_app(provider: ChannelAppProvider, request: Request) -> None:
    deleted = await request.app.state.channel_app_repo.delete(provider)
    if not deleted:
        raise HTTPException(status_code=404, detail="channel_app not found")
