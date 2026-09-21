"""Use case: sign a user in with email and password."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases._auth_common import build_authenticated_user
from app.domain.ports.outbound import (
    AuthSessionRepositoryPort,
    LoginThrottlePort,
    PasswordHasherPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

__all__ = ["AuthenticateUserUseCase", "InvalidCredentialsError", "TooManyAttemptsError"]

logger = logging.getLogger("auth.login")


class InvalidCredentialsError(Exception):
    """Wrong email/password, or the account is disabled.

    Deliberately indistinguishable across those cases so the endpoint
    does not reveal which emails exist.
    """


class TooManyAttemptsError(Exception):
    """Too many recent failures for this account or client IP."""


class AuthenticateUserUseCase:
    """Verifies credentials and opens a server-side session.

    Defences: per-account and per-IP failure throttling; a dummy hash
    check when the email is unknown so response time does not reveal
    whether the account exists; disabled accounts look like wrong
    passwords. Hashing runs in a worker thread because scrypt is CPU
    heavy and would otherwise stall the event loop.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        hasher: PasswordHasherPort,
        sessions: AuthSessionRepositoryPort,
        throttle: LoginThrottlePort,
        session_ttl_seconds: int,
        window_seconds: int,
        max_failures_per_email: int,
        max_failures_per_ip: int,
    ) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Loads users and their hashes.
            tenant_repo (TenantRepositoryPort): Resolves the user's tenants.
            hasher (PasswordHasherPort): Verifies passwords.
            sessions (AuthSessionRepositoryPort): Opens the session.
            throttle (LoginThrottlePort): Failed-login counters.
            session_ttl_seconds (int): Idle lifetime of the new session.
            window_seconds (int): Throttle window.
            max_failures_per_email (int): Failures per account before blocking.
            max_failures_per_ip (int): Failures per client IP before blocking.
        """
        self._user_repo = user_repo
        self._tenant_repo = tenant_repo
        self._hasher = hasher
        self._sessions = sessions
        self._throttle = throttle
        self._ttl = session_ttl_seconds
        self._window = window_seconds
        self._max_email = max_failures_per_email
        self._max_ip = max_failures_per_ip
        # Hash of a random string, used to spend the same time on unknown emails.
        self._dummy_hash = hasher.hash("dummy-password-for-timing-equalization")

    async def execute(
        self, *, email: str, password: str, client_ip: Optional[str] = None
    ) -> Tuple[str, AuthenticatedUser]:
        """Authenticate and open a session.

        Args:
            email (str): Email typed by the user (case-insensitive).
            password (str): Plaintext password.
            client_ip (Optional[str]): Caller's IP, for the per-IP throttle.

        Returns:
            Tuple[str, AuthenticatedUser]: The opaque session token (to
            put in the cookie) and the signed-in user.

        Raises:
            TooManyAttemptsError: If the account or IP hit its failure limit.
            InvalidCredentialsError: If the credentials are wrong or the
                account is disabled.
        """
        email = email.strip().lower()
        email_key = f"email:{email}"
        ip_key = f"ip:{client_ip}" if client_ip else None

        if await self._throttle.failures(email_key) >= self._max_email:
            raise TooManyAttemptsError()
        if ip_key and await self._throttle.failures(ip_key) >= self._max_ip:
            raise TooManyAttemptsError()

        creds = await self._user_repo.get_credentials_by_email(email)
        stored_hash = creds.password_hash if creds else self._dummy_hash
        matches = await asyncio.to_thread(self._hasher.verify, password, stored_hash)

        if not creds or not matches or not creds.user.is_active:
            await self._throttle.record_failure(email_key, window_seconds=self._window)
            if ip_key:
                await self._throttle.record_failure(ip_key, window_seconds=self._window)
            logger.info("auth.login.failed", extra={"client_ip": client_ip})
            raise InvalidCredentialsError()

        await self._throttle.reset(email_key)
        token = await self._sessions.create(creds.user.id, ttl_seconds=self._ttl)
        await self._user_repo.mark_login(creds.user.id)
        logger.info("auth.login.success", extra={"user_id": str(creds.user.id)})
        return token, await build_authenticated_user(creds.user, self._tenant_repo)
