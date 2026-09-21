"""Use case: resolve the signed-in user from a session token."""

from __future__ import annotations

from typing import Optional

from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.domain.ports.outbound import (
    AuthSessionRepositoryPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

__all__ = ["GetCurrentUserUseCase"]


class GetCurrentUserUseCase:
    """Turns a session token into the current user, sliding the session
    forward. The user is re-read from the database on every call, so
    role/tenant changes and account disabling apply immediately.
    """

    def __init__(
        self,
        *,
        sessions: AuthSessionRepositoryPort,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        session_ttl_seconds: int,
    ) -> None:
        """Build the use case.

        Args:
            sessions (AuthSessionRepositoryPort): Resolves tokens.
            user_repo (UserRepositoryPort): Loads the user.
            tenant_repo (TenantRepositoryPort): Resolves the user's tenants.
            session_ttl_seconds (int): Idle lifetime applied on each use.
        """
        self._sessions = sessions
        self._user_repo = user_repo
        self._tenant_repo = tenant_repo
        self._ttl = session_ttl_seconds

    async def execute(self, token: Optional[str]) -> Optional[AuthenticatedUser]:
        """Resolve the current user.

        Args:
            token (Optional[str]): Session token from the cookie, if any.

        Returns:
            Optional[AuthenticatedUser]: The user, or None if there is no
            valid session or the account has been disabled/removed (in
            which case the stale session is also closed).
        """
        if not token:
            return None
        user_id = await self._sessions.get_user_id(token, ttl_seconds=self._ttl)
        if user_id is None:
            return None
        user = await self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            await self._sessions.delete(token)
            return None
        return await build_authenticated_user(user, self._tenant_repo)
