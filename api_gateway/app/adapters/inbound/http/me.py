"""Self-service endpoints for the signed-in user's own data.

Unlike `/internal/admin/*`, these never go through `POLICY`/`AccessControl`:
they only ever act on the caller's own session, so there is nothing to scope
by role - any signed-in user (client and consultant included, who otherwise
never touch the admin API at all) can call them. Keep this router for data
that is inherently "about me", not a general-purpose escape hatch around
`POLICY`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.adapters.inbound.http.admin.schemas import ProfileUpdate, TenantBillingOut
from app.adapters.inbound.http.auth_deps import get_current_user, require_console_header
from app.adapters.inbound.http.avatar_io import avatar_response, read_image_body
from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.application.use_cases.manage_profile import InvalidAvatarError

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/billing-profile", response_model=TenantBillingOut)
async def my_billing_profile(
    request: Request, user: AuthenticatedUser = Depends(get_current_user)
) -> TenantBillingOut:
    """Billing/company data of the caller's own tenant (read-only).

    Built for `client` (see `TenantBillingProfile`): the tenant is whichever
    one the caller belongs to, resolved from the session - never a path
    parameter, so there is no tenant to scope-check.

    Args:
        request (Request): Used to reach `request.app.state.tenant_billing_profile_repo`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        TenantBillingOut: The profile - all fields `None` if nothing was
        filled in yet.

    Raises:
        HTTPException: 404 if the caller belongs to no tenant (shouldn't
            happen for `client`/`consultant` in practice, but `admin` has
            none by design and would hit this too).
    """
    if not user.tenants:
        raise HTTPException(status_code=404, detail="no tenant for this account")
    tenant_id = user.tenants[0].id
    repo = request.app.state.tenant_billing_profile_repo
    profile = await repo.get_by_tenant_id(tenant_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no billing profile yet")
    return TenantBillingOut(**profile.model_dump())


@router.patch("/profile", response_model=AuthenticatedUser, dependencies=[Depends(require_console_header)])
async def update_my_profile(
    body: ProfileUpdate, request: Request, user: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """Edit the caller's own name and optional profile data.

    Email, role and tenants are not editable here (admin API only).

    Args:
        body (ProfileUpdate): Fields to change; unset fields stay as they are.
        request (Request): Used to reach `request.app.state.update_own_profile_use_case`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        AuthenticatedUser: The updated user, same shape as `GET /auth/me`.

    Raises:
        HTTPException: 400 on invalid input, 401 without a session, 403
            without the console header.
    """
    try:
        updated = await request.app.state.update_own_profile_use_case.execute(
            user.id, **body.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return updated


@router.get("/avatar")
async def my_avatar(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    """The caller's profile photo.

    Args:
        request (Request): Used to reach `request.app.state.user_avatar_repo`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        Response: The image.

    Raises:
        HTTPException: 404 if the caller has no photo.
    """
    avatar = await request.app.state.user_avatar_repo.get(user.id)
    if avatar is None:
        raise HTTPException(status_code=404, detail="no avatar")
    return avatar_response(avatar)


@router.put("/avatar", response_model=AuthenticatedUser, dependencies=[Depends(require_console_header)])
async def set_my_avatar(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Set (or replace) the caller's photo; the body is the raw image.

    Args:
        request (Request): The upload; also reaches `set_avatar_use_case`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        AuthenticatedUser: The updated user (new `avatar_updated_at`).

    Raises:
        HTTPException: 400 if it is not a JPEG/PNG/WebP image, 413 if too large.
    """
    data = await read_image_body(request)
    try:
        updated = await request.app.state.set_avatar_use_case.execute(user.id, data)
    except InvalidAvatarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return await build_authenticated_user(updated, request.app.state.tenant_repo)


@router.delete("/avatar", response_model=AuthenticatedUser, dependencies=[Depends(require_console_header)])
async def remove_my_avatar(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Remove the caller's photo (idempotent).

    Args:
        request (Request): Used to reach `request.app.state.remove_avatar_use_case`.
        user (AuthenticatedUser): The signed-in user.

    Returns:
        AuthenticatedUser: The updated user (`avatar_updated_at` = null).
    """
    updated = await request.app.state.remove_avatar_use_case.execute(user.id)
    if updated is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return await build_authenticated_user(updated, request.app.state.tenant_repo)
