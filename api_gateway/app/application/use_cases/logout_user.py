"""Use case: sign a user out."""

from __future__ import annotations

from typing import Optional

from app.domain.ports.outbound import AuthSessionRepositoryPort

__all__ = ["LogoutUserUseCase"]


class LogoutUserUseCase:
    """Closes the server-side session so the token stops working even if
    someone kept a copy of the cookie."""

    def __init__(self, *, sessions: AuthSessionRepositoryPort) -> None:
        """Build the use case.

        Args:
            sessions (AuthSessionRepositoryPort): Store to delete from.
        """
        self._sessions = sessions

    async def execute(self, token: Optional[str]) -> None:
        """Invalidate a session (idempotent; unknown tokens are ignored).

        Args:
            token (Optional[str]): Session token from the cookie, if any.
        """
        if token:
            await self._sessions.delete(token)
