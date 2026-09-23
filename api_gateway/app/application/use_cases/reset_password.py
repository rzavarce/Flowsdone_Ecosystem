"""Use case: redeem a password-reset token and set a new password."""

from __future__ import annotations

import asyncio
from typing import Tuple

from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.application.use_cases.activate_account import InvalidTokenError
from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH
from app.domain.ports.outbound import (
    AccountTokenStorePort,
    AuthSessionRepositoryPort,
    PasswordHasherPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

__all__ = ["ResetPasswordUseCase"]


class ResetPasswordUseCase:
    """Sets a new password for a user who proved control of their inbox via
    the reset link, and opens a fresh session (auto-login) the same way
    `ActivateAccountUseCase` does.
    """

    def __init__(
        self,
        *,
        tokens: AccountTokenStorePort,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        hasher: PasswordHasherPort,
        sessions: AuthSessionRepositoryPort,
        session_ttl_seconds: int,
    ) -> None:
        """Build the use case.

        Args:
            tokens (AccountTokenStorePort): Redeems the reset token (expected
                to be scoped to reset, not activation).
            user_repo (UserRepositoryPort): Loads and persists the user.
            tenant_repo (TenantRepositoryPort): Resolves tenants for the
                auto-login response.
            hasher (PasswordHasherPort): Hashes the new password.
            sessions (AuthSessionRepositoryPort): Closes old sessions, opens
                the new one.
            session_ttl_seconds (int): Idle lifetime of the new session.
        """
        self._tokens = tokens
        self._users = user_repo
        self._tenants = tenant_repo
        self._hasher = hasher
        self._sessions = sessions
        self._session_ttl = session_ttl_seconds

    async def execute(self, *, token: str, password: str) -> Tuple[str, AuthenticatedUser]:
        """Set the new password and sign the user in.

        Args:
            token (str): The value from the reset link.
            password (str): The new password.

        Returns:
            Tuple[str, AuthenticatedUser]: The opaque session token (to put
            in the cookie) and the user.

        Raises:
            ValueError: If the password is shorter than `MIN_PASSWORD_LENGTH`.
            InvalidTokenError: If the token is invalid/expired, or the
                account is not `active` (still `pending`, or disabled).
        """
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

        user_id = await self._tokens.redeem(token)
        if user_id is None:
            raise InvalidTokenError()
        user = await self._users.get_by_id(user_id)
        if user is None or user.status != "active":
            raise InvalidTokenError()

        password_hash = await asyncio.to_thread(self._hasher.hash, password)
        updated = await self._users.update(user.id, password_hash=password_hash)
        assert updated is not None

        await self._sessions.delete_all_for_user(user.id)
        session_token = await self._sessions.create(user.id, ttl_seconds=self._session_ttl)
        await self._users.mark_login(user.id)
        return session_token, await build_authenticated_user(updated, self._tenants)
