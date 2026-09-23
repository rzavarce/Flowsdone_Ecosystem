"""FastAPI dependencies that protect endpoints with the console session.

Use `Depends(get_current_user)` to require a signed-in user, and
`Depends(require_roles("admin", ...))` to also restrict by role. Use
`ensure_tenant_access` for endpoints that act on one tenant. These are the
building blocks for guarding the admin API with user sessions instead of
the shared `X-Admin-Api-Key`.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request

from app.application.dto.auth_dto import AuthenticatedUser
from app.core.config import settings


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Require a valid session cookie and return its user.

    Args:
        request (Request): The incoming request; the token is read from the
            cookie named by `settings.AUTH_COOKIE_NAME`.

    Returns:
        AuthenticatedUser: The signed-in user.

    Raises:
        HTTPException: 401 if there is no valid session.
    """
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    user = await request.app.state.get_current_user_use_case.execute(token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def require_roles(*roles: str) -> Callable[..., AuthenticatedUser]:
    """Build a dependency that only lets the given roles through.

    Args:
        *roles (str): Allowed roles (e.g. `"admin", "tenant_manager"`).

    Returns:
        Callable: A FastAPI dependency resolving to the current user.
        It raises 401 without a session and 403 for another role.
    """

    async def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return dependency


def ensure_tenant_access(user: AuthenticatedUser, tenant_id: UUID) -> None:
    """Check the user may act on a tenant.

    Args:
        user (AuthenticatedUser): The signed-in user.
        tenant_id (UUID): Tenant the request targets.

    Raises:
        HTTPException: 403 unless the user is an `admin` or a member of
            that tenant.
    """
    if user.role == "admin":
        return
    if not any(t.id == tenant_id for t in user.tenants):
        raise HTTPException(status_code=403, detail="forbidden")


CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "fd-console"


def require_console_header(request: Request) -> None:
    """CSRF guard for cookie-authenticated requests that change state.

    Same rule as the admin API (see `admin/access.py`): a browser will not
    add a custom header to a cross-site request without a CORS preflight,
    which this API never grants.

    Args:
        request (Request): The incoming request.

    Raises:
        HTTPException: 403 if `X-Requested-With: fd-console` is missing.
    """
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status_code=403, detail="missing X-Requested-With header")
