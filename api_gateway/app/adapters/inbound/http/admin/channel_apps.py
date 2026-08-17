"""Admin CRUD endpoints for shared provider app credentials."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api_gateway.app.domain.models.channel_app import ChannelApp, ChannelAppProvider
from api_gateway.app.adapters.inbound.http.admin.auth import require_admin_api_key
from api_gateway.app.adapters.inbound.http.admin.schemas import ChannelAppCredentialsOut, ChannelAppOut, ChannelAppUpsert

router = APIRouter(
    prefix="/channel-apps",
    tags=["admin:channel-apps"],
    dependencies=[Depends(require_admin_api_key)],
)


def _to_out(channel_app: ChannelApp) -> ChannelAppOut:
    """Convert a ChannelApp domain object into its response schema,
    stripping raw credentials.

    Args:
        channel_app (ChannelApp): The domain object to convert.

    Returns:
        ChannelAppOut: The response schema, without credentials.
    """
    data = channel_app.model_dump(exclude={"credentials"})
    return ChannelAppOut(**data, has_credentials=bool(channel_app.credentials))


@router.get("", response_model=list[ChannelAppOut])
async def list_channel_apps(request: Request) -> list[ChannelAppOut]:
    """List all provider app credential records.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_app_repo`.

    Returns:
        list[ChannelAppOut]: All existing channel app records.
    """
    channel_apps = await request.app.state.channel_app_repo.list()
    return [_to_out(a) for a in channel_apps]


@router.get("/{provider}", response_model=ChannelAppOut)
async def get_channel_app(provider: ChannelAppProvider, request: Request) -> ChannelAppOut:
    """Fetch a provider's app credentials.

    Args:
        provider (ChannelAppProvider): Provider identifier.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_app_repo`.

    Returns:
        ChannelAppOut: The matching channel app.

    Raises:
        HTTPException: 404 if not configured.
    """
    channel_app = await request.app.state.channel_app_repo.get_by_provider(provider)
    if not channel_app:
        raise HTTPException(status_code=404, detail="channel_app not found")
    return _to_out(channel_app)


@router.get("/{provider}/credentials", response_model=ChannelAppCredentialsOut)
async def reveal_channel_app_credentials(
    provider: ChannelAppProvider, request: Request
) -> ChannelAppCredentialsOut:
    """Fetch a provider's app credentials in plain text.

    Exists so an admin can retrieve a server-generated value (e.g.
    Meta's auto-generated `webhook_verify_token`) that was never typed
    in by anyone and would otherwise be unrecoverable after creation -
    ChannelAppOut/`_to_out` deliberately strip credentials.

    Args:
        provider (ChannelAppProvider): Provider identifier.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_app_repo`.

    Returns:
        ChannelAppCredentialsOut: The provider and its credentials.

    Raises:
        HTTPException: 404 if not configured.
    """
    channel_app = await request.app.state.channel_app_repo.get_by_provider(provider)
    if not channel_app:
        raise HTTPException(status_code=404, detail="channel_app not found")
    return ChannelAppCredentialsOut(provider=channel_app.provider, credentials=channel_app.credentials)


@router.put("/{provider}", response_model=ChannelAppOut)
async def upsert_channel_app(
    provider: ChannelAppProvider, body: ChannelAppUpsert, request: Request
) -> ChannelAppOut:
    """Create or replace a provider's shared app credentials.

    Args:
        provider (ChannelAppProvider): Provider identifier.
        body (ChannelAppUpsert): Credentials and configuration to store.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_app_repo`.

    Returns:
        ChannelAppOut: The upserted channel app.
    """
    channel_app = await request.app.state.upsert_channel_app_use_case.execute(
        provider=provider, credentials=body.credentials, config=body.config
    )
    return _to_out(channel_app)


@router.delete("/{provider}", status_code=204)
async def delete_channel_app(provider: ChannelAppProvider, request: Request) -> None:
    """Delete a provider's app credentials.

    Args:
        provider (ChannelAppProvider): Provider identifier.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.channel_app_repo`.

    Raises:
        HTTPException: 404 if not configured.
    """
    deleted = await request.app.state.channel_app_repo.delete(provider)
    if not deleted:
        raise HTTPException(status_code=404, detail="channel_app not found")
