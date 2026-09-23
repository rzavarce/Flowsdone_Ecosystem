"""Admin endpoints to manage console users. `admin` (or the API key) only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import UserCreate, UserOut, UserUpdate
from app.adapters.inbound.http.avatar_io import avatar_response, read_image_body
from app.application.use_cases.manage_profile import InvalidAvatarError, normalize_profile_fields
from app.application.use_cases.manage_users import SelfLockoutError
from app.domain.ports.outbound import EmailSendError, UserAlreadyExistsError

router = APIRouter(prefix="/users", tags=["admin:users"])


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> UserOut:
    """Create a console user and start their email-activation flow.

    No password is set here: the user is created `pending` and emailed an
    activation link to choose their own (see `ProvisionUserUseCase`).

    Args:
        body (UserCreate): The new user's fields.
        request (Request): Used to reach `request.app.state.provision_user_use_case`
            (and `update_user_use_case` to store the optional profile fields).
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The created (pending) user.

    Raises:
        HTTPException: 400 on invalid input (role, tenants…), 409 if the
            email is already registered, 502 if the user was created but
            the activation email could not be sent (retry via
            `POST /users/{id}/resend-activation`).
    """
    profile = body.model_dump(include={"phone", "address", "social_links"}, exclude_none=True)
    try:
        # Validated up front so a bad phone/URL never leaves a half-created user behind.
        normalize_profile_fields(**profile)
        user = await request.app.state.provision_user_use_case.execute(
            email=body.email,
            name=body.name,
            role=body.role,
            tenant_ids=body.tenant_ids,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="a user with that email already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmailSendError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"user created but the activation email could not be sent: {exc}",
        ) from exc
    if profile:
        user = await request.app.state.update_user_use_case.execute(user.id, **profile) or user
    return UserOut(**user.model_dump())


@router.get("", response_model=list[UserOut])
async def list_users(
    request: Request, access: AdminAccess = Depends(admin_access("users", "read"))
) -> list[UserOut]:
    """List all console users.

    Args:
        request (Request): Used to reach `request.app.state.user_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        list[UserOut]: Every user, oldest first.
    """
    users = await request.app.state.user_repo.list()
    return [UserOut(**u.model_dump()) for u in users]


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "read"))
) -> UserOut:
    """Fetch a user by id.

    Args:
        user_id (UUID): Id of the user.
        request (Request): Used to reach `request.app.state.user_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The user.

    Raises:
        HTTPException: 404 if it does not exist.
    """
    user = await request.app.state.user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(**user.model_dump())


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    request: Request,
    access: AdminAccess = Depends(admin_access("users", "write")),
) -> UserOut:
    """Update a user; role, tenant, status or password changes take effect at once.

    Args:
        user_id (UUID): Id of the user.
        body (UserUpdate): Fields to change; unset fields stay as they are.
        request (Request): Used to reach `request.app.state.update_user_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The updated user.

    Raises:
        HTTPException: 404 if it does not exist, 400 on invalid input, 409 if
            an admin tries to disable or demote themselves.
    """
    try:
        user = await request.app.state.update_user_use_case.execute(
            user_id, actor_id=access.principal.user_id, **body.model_dump(exclude_unset=True)
        )
    except SelfLockoutError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(**user.model_dump())


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> None:
    """Delete a user and close their sessions.

    Args:
        user_id (UUID): Id of the user.
        request (Request): Used to reach `request.app.state.delete_user_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Raises:
        HTTPException: 404 if it does not exist, 409 if an admin tries to
            delete themselves.
    """
    try:
        deleted = await request.app.state.delete_user_use_case.execute(
            user_id, actor_id=access.principal.user_id
        )
    except SelfLockoutError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="user not found")


@router.post("/{user_id}/resend-activation", status_code=204)
async def resend_activation(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> None:
    """Re-send the activation email to a user still `pending`.

    Covers a link lost or caught by spam within its lifetime, without
    having to delete and recreate the user.

    Args:
        user_id (UUID): Id of the user.
        request (Request): Used to reach `request.app.state.provision_user_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Raises:
        HTTPException: 404 if the user does not exist or is no longer
            `pending` (already active/disabled - indistinguishable on
            purpose), 502 if the email could not be sent.
    """
    try:
        sent = await request.app.state.provision_user_use_case.resend_activation(user_id)
    except EmailSendError as exc:
        raise HTTPException(status_code=502, detail=f"could not send the activation email: {exc}") from exc
    if not sent:
        raise HTTPException(status_code=404, detail="user not found or not pending")


@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "read"))
) -> Response:
    """A user's profile photo.

    Args:
        user_id (UUID): Id of the user.
        request (Request): Used to reach `request.app.state.user_avatar_repo`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        Response: The image.

    Raises:
        HTTPException: 404 if the user has no photo (or does not exist).
    """
    avatar = await request.app.state.user_avatar_repo.get(user_id)
    if avatar is None:
        raise HTTPException(status_code=404, detail="no avatar")
    return avatar_response(avatar)


@router.put("/{user_id}/avatar", response_model=UserOut)
async def set_user_avatar(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> UserOut:
    """Set (or replace) a user's photo; the body is the raw image.

    Args:
        user_id (UUID): Id of the user.
        request (Request): The upload; also reaches `set_avatar_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The updated user.

    Raises:
        HTTPException: 400 if not a JPEG/PNG/WebP image, 404 if the user
            does not exist, 413 if too large.
    """
    data = await read_image_body(request)
    try:
        user = await request.app.state.set_avatar_use_case.execute(user_id, data)
    except InvalidAvatarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(**user.model_dump())


@router.delete("/{user_id}/avatar", response_model=UserOut)
async def remove_user_avatar(
    user_id: UUID, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> UserOut:
    """Remove a user's photo (idempotent).

    Args:
        user_id (UUID): Id of the user.
        request (Request): Used to reach `request.app.state.remove_avatar_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The updated user.

    Raises:
        HTTPException: 404 if the user does not exist.
    """
    user = await request.app.state.remove_avatar_use_case.execute(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut(**user.model_dump())
