"""Use case: redeem an account-activation token and set the user's password."""

from __future__ import annotations

import asyncio
from typing import Tuple

from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH
from app.domain.ports.outbound import (
    AccountTokenStorePort,
    AuthSessionRepositoryPort,
    PasswordHasherPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

__all__ = ["ActivateAccountUseCase", "InvalidTokenError"]


class InvalidTokenError(Exception):
    """The token is unknown, already used, expired, or its account is no
    longer in the state this use case expects.

    Deliberately a single, generic error for all of those cases (also
    reused by `ResetPasswordUseCase`) - the caller can't tell "expired" from
    "the account got disabled in between" from "this token doesn't exist",
    which is the point: nothing about the account should leak from this
    endpoint.
    """


class ActivateAccountUseCase:
    """Turns a `pending` user into `active`, with the password they choose.

    The activation link itself already proved the person controls that
    inbox, so on success this also opens a session (auto-login) - the same
    shape `AuthenticateUserUseCase` returns, so the endpoint can set the
    cookie the same way `/auth/login` does.
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
            tokens (AccountTokenStorePort): Redeems the activation token
                (expected to be scoped to activation, not reset).
            user_repo (UserRepositoryPort): Loads and persists the user.
            tenant_repo (TenantRepositoryPort): Resolves the user's tenants
                for the auto-login response.
            hasher (PasswordHasherPort): Hashes the chosen password.
            sessions (AuthSessionRepositoryPort): Opens the new session.
            session_ttl_seconds (int): Idle lifetime of that session.
        """
        self._tokens = tokens
        self._users = user_repo
        self._tenants = tenant_repo
        self._hasher = hasher
        self._sessions = sessions
        self._session_ttl = session_ttl_seconds

    async def execute(self, *, token: str, password: str) -> Tuple[str, AuthenticatedUser]:
        """Activate the account and sign the user in.

        Args:
            token (str): The value from the activation link.
            password (str): The password the user is choosing.

        Returns:
            Tuple[str, AuthenticatedUser]: The opaque session token (to put
            in the cookie) and the now-active user.

        Raises:
            ValueError: If the password is shorter than `MIN_PASSWORD_LENGTH`.
            InvalidTokenError: If the token is invalid/expired, or the
                account is no longer `pending` (already activated, or
                disabled in the meantime).
        """
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

        user_id = await self._tokens.redeem(token)
        if user_id is None:
            raise InvalidTokenError()
        user = await self._users.get_by_id(user_id)
        if user is None or user.status != "pending":
            raise InvalidTokenError()

        password_hash = await asyncio.to_thread(self._hasher.hash, password)
        updated = await self._users.update(user_id, status="active", password_hash=password_hash)
        assert updated is not None  # just loaded it above; nothing else can delete it concurrently here

        # Defensive: a pending user shouldn't have live sessions, but this
        # keeps the invariant "a password change closes old sessions" true
        # everywhere, same as UpdateUserUseCase/ResetPasswordUseCase.
        await self._sessions.delete_all_for_user(user_id)
        session_token = await self._sessions.create(user_id, ttl_seconds=self._session_ttl)
        await self._users.mark_login(user_id)
        return session_token, await build_authenticated_user(updated, self._tenants)
