"""Access control for the admin API: identify the caller, authorize the role,
and hand routers a scoped helper.

A caller is either
- a **machine** presenting the shared `X-Admin-Api-Key` (scripts, CI, Postman;
  treated as an unrestricted admin, exactly as before), or
- a **console user** with a session cookie, subject to `POLICY` and to the
  tenants they belong to.

Cookie-authenticated requests that change state must also carry
`X-Requested-With: fd-console`. A browser will not add a custom header to a
cross-site request without a CORS preflight, and this API grants none, so it
closes CSRF from sibling subdomains (`chat.`, `platform.`… share the same
"site" and are therefore not covered by `SameSite=Lax` alone). API-key
callers are not browsers and are exempt.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, List, Optional
from uuid import UUID

from fastapi import Header, HTTPException, Request

from app.adapters.inbound.http.admin.auth import is_valid_admin_api_key
from app.application.services.access_control import (
    AccessControl,
    AccessDeniedError,
    InvalidReferenceError,
    Principal,
    ResourceNotFoundError,
)
from app.core.config import settings
from app.domain.models.project import Project

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "fd-console"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AdminAccess:
    """What a handler gets after authentication: the caller plus scoping
    helpers that turn domain errors into the right HTTP status.
    """

    def __init__(self, principal: Principal, control: AccessControl) -> None:
        """Build the helper.

        Args:
            principal (Principal): The authenticated caller.
            control (AccessControl): The authorization service.
        """
        self.principal = principal
        self._control = control

    @property
    def unrestricted(self) -> bool:
        """True when the caller sees every tenant (admin or API key)."""
        return self.principal.unrestricted

    def tenant(self, tenant_id: UUID, *, resource: str = "tenant") -> None:
        """Require a tenant inside the caller's scope.

        Args:
            tenant_id (UUID): Tenant to check.
            resource (str): Name used in the 404 message.

        Raises:
            HTTPException: 404 if it is out of scope.
        """
        try:
            self._control.ensure_tenant(self.principal, tenant_id, resource=resource)
        except ResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def project(self, project_id: UUID, *, resource: str = "project") -> Project:
        """Require a project that exists inside the caller's scope.

        Args:
            project_id (UUID): Project to check.
            resource (str): What the caller asked for, for the 404 message.

        Returns:
            Project: The project.

        Raises:
            HTTPException: 404 if it does not exist or is out of scope.
        """
        try:
            return await self._control.ensure_project(self.principal, project_id, resource=resource)
        except ResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def visible_projects(self) -> List[Project]:
        """Projects of every tenant the caller can see.

        Returns:
            List[Project]: All projects for unrestricted callers; otherwise
            those of the caller's tenants.
        """
        return await self._control.visible_projects(self.principal)

    async def list_by_project(
        self,
        list_fn: Callable[[Optional[UUID]], Awaitable[List[Any]]],
        project_id: Optional[UUID],
        *,
        resource: str,
    ) -> List[Any]:
        """List project-owned items limited to the caller's tenants.

        Args:
            list_fn (Callable): A repository's `list_by_project`.
            project_id (Optional[UUID]): Optional query filter.
            resource (str): Name used in the 404 message.

        Returns:
            List[Any]: The items the caller may see.

        Raises:
            HTTPException: 404 if `project_id` is out of scope.
        """
        try:
            return await self._control.list_scoped(
                self.principal, list_fn, project_id, resource=resource
            )
        except ResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def agent_in_project(self, agent_id: UUID, project_id: UUID) -> None:
        """Require the agent to belong to the project (cross-tenant guard).

        Args:
            agent_id (UUID): Agent referenced by the request body.
            project_id (UUID): Project the channel belongs to.

        Raises:
            HTTPException: 400 if it does not.
        """
        try:
            await self._control.ensure_agent_in_project(agent_id, project_id)
        except InvalidReferenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


async def resolve_principal(request: Request, api_key: Optional[str]) -> Principal:
    """Identify the caller from the API key or the session cookie.

    Args:
        request (Request): The incoming request.
        api_key (Optional[str]): Value of `X-Admin-Api-Key`, if sent.

    Returns:
        Principal: The caller.

    Raises:
        HTTPException: 401 if neither credential is valid (a wrong API key
            is rejected outright, never "downgraded" to the cookie); 403 if
            a cookie-authenticated state-changing request lacks the CSRF header.
    """
    if api_key is not None:
        if not is_valid_admin_api_key(api_key):
            raise HTTPException(status_code=401, detail="invalid admin api key")
        return Principal.machine()

    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    user = await request.app.state.get_current_user_use_case.execute(token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")

    if request.method in _UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status_code=403, detail="missing CSRF header")
    return Principal.from_user(user)


def admin_access(resource: str, action: str) -> Callable[..., Awaitable[AdminAccess]]:
    """Build a dependency: authenticate, then authorize `action` on `resource`.

    Args:
        resource (str): A key of `access_control.POLICY`.
        action (str): `read` or `write`.

    Returns:
        Callable: A FastAPI dependency resolving to an `AdminAccess`. It
        raises 401 (no/invalid credentials), 403 (role not allowed, or CSRF).
    """

    async def dependency(
        request: Request, x_admin_api_key: Optional[str] = Header(default=None)
    ) -> AdminAccess:
        control: AccessControl = request.app.state.access_control
        principal = await resolve_principal(request, x_admin_api_key)
        try:
            control.authorize(principal, resource, action)
        except AccessDeniedError as exc:
            raise HTTPException(status_code=403, detail="forbidden") from exc
        return AdminAccess(principal, control)

    return dependency
