"""Use case: request a password-reset email ("forgot my password")."""

from __future__ import annotations

from typing import Optional

from app.domain.ports.outbound import (
    AccountTokenStorePort,
    EmailSenderPort,
    LoginThrottlePort,
    UserRepositoryPort,
)

__all__ = ["RequestPasswordResetUseCase", "TooManyAttemptsError"]


class TooManyAttemptsError(Exception):
    """Too many recent reset requests for this account or client IP."""


class RequestPasswordResetUseCase:
    """Emails a reset link if, and only if, the account exists and is active.

    Always *behaves* the same either way (returns normally, never raises for
    an unknown email) so the endpoint can answer identically regardless -
    same anti-enumeration principle `AuthenticateUserUseCase` uses for login.
    `LoginThrottlePort` is reused as a plain request counter (its `key`/
    `window_seconds` shape doesn't care that it was named for login
    failures) to stop someone from spamming an inbox with reset emails.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepositoryPort,
        tokens: AccountTokenStorePort,
        mailer: EmailSenderPort,
        throttle: LoginThrottlePort,
        ttl_seconds: int,
        reset_base_url: str,
        window_seconds: int,
        max_requests_per_email: int,
        max_requests_per_ip: int,
    ) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Looks the account up by email.
            tokens (AccountTokenStorePort): Issues the reset token (expected
                to be scoped to reset, not activation).
            mailer (EmailSenderPort): Sends the reset email.
            throttle (LoginThrottlePort): Request-rate counters.
            ttl_seconds (int): Reset link lifetime.
            reset_base_url (str): Public origin the link is built against
                (`{reset_base_url}/reset-password/{token}`).
            window_seconds (int): Throttle window.
            max_requests_per_email (int): Requests per account before blocking.
            max_requests_per_ip (int): Requests per client IP before blocking.
        """
        self._users = user_repo
        self._tokens = tokens
        self._mailer = mailer
        self._throttle = throttle
        self._ttl = ttl_seconds
        self._base_url = reset_base_url.rstrip("/")
        self._window = window_seconds
        self._max_email = max_requests_per_email
        self._max_ip = max_requests_per_ip

    async def execute(self, *, email: str, client_ip: Optional[str] = None) -> None:
        """Send the reset email if the account exists and is active.

        Args:
            email (str): Email typed by the user.
            client_ip (Optional[str]): Caller's IP, for the per-IP throttle.

        Raises:
            TooManyAttemptsError: If the account or IP hit its request limit.
        """
        email = email.strip().lower()
        email_key = f"reset-req:email:{email}"
        ip_key = f"reset-req:ip:{client_ip}" if client_ip else None

        if await self._throttle.failures(email_key) >= self._max_email:
            raise TooManyAttemptsError()
        if ip_key and await self._throttle.failures(ip_key) >= self._max_ip:
            raise TooManyAttemptsError()

        # Counted unconditionally, whether or not the account exists below -
        # otherwise response timing/throttle state would leak which emails
        # are registered.
        await self._throttle.record_failure(email_key, window_seconds=self._window)
        if ip_key:
            await self._throttle.record_failure(ip_key, window_seconds=self._window)

        creds = await self._users.get_credentials_by_email(email)
        if creds is None or not creds.user.is_active:
            return

        token = await self._tokens.issue(creds.user.id, ttl_seconds=self._ttl)
        link = f"{self._base_url}/reset-password/{token}"
        await self._mailer.send_template(
            to=creds.user.email,
            template="password_reset",
            context={"name": creds.user.name, "link": link, "ttl_hours": max(1, self._ttl // 3600)},
            subject="Restablece tu contraseña de Flowsdone",
        )
