"""Admin endpoints to manage console users. `admin` (or the API key) only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.inbound.http.admin.access import AdminAccess, admin_access
from app.adapters.inbound.http.admin.schemas import UserCreate, UserOut, UserUpdate
from app.application.use_cases.manage_users import SelfLockoutError
from app.domain.ports.outbound import UserAlreadyExistsError

router = APIRouter(prefix="/users", tags=["admin:users"])


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate, request: Request, access: AdminAccess = Depends(admin_access("users", "write"))
) -> UserOut:
    """Create a console user.

    Args:
        body (UserCreate): The new user's fields.
        request (Request): Used to reach `request.app.state.create_user_use_case`.
        access (AdminAccess): The authenticated caller (admin only).

    Returns:
        UserOut: The created user (no password hash).

    Raises:
        HTTPException: 400 on invalid input (role, password length, tenants…),
            409 if the email is already registered.
    """
    try:
        user = await request.app.state.create_user_use_case.execute(
            email=body.email,
            name=body.name,
            role=body.role,
            password=body.password,
            tenant_ids=body.tenant_ids,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="a user with that email already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
