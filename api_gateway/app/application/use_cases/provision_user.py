"""Use case: create a user and start their email-activation flow.

Composes `CreateUserUseCase` (validation + persistence) with
`AccountTokenStorePort` (single-use activation token) and `EmailSenderPort`
(the actual email) so nobody - admin creating staff, or a tenant's freshly
created client - ever receives a plaintext password. The user is created
`pending` with an unusable, randomly generated password; the real one is
whatever they set when they redeem the activation link (see
`ActivateAccountUseCase`).

Used by both `POST /internal/admin/users` and `CreateTenantUseCase` (for the
tenant's `client` user), so this glue lives in exactly one place.
"""

from __future__ import annotations

import secrets
from typing import List
from uuid import UUID

from app.domain.models.user import User
from app.domain.ports.outbound import AccountTokenStorePort, EmailSenderPort, UserRepositoryPort
from app.application.use_cases.create_user import CreateUserUseCase

__all__ = ["ProvisionUserUseCase"]

# Never seen by anyone - only satisfies the NOT NULL password_hash column
# until the user sets their own on activation.
_RANDOM_PASSWORD_LENGTH = 32


class ProvisionUserUseCase:
    """Creates a pending user and emails them their activation link."""

    def __init__(
        self,
        *,
        create_user: CreateUserUseCase,
        user_repo: UserRepositoryPort,
        tokens: AccountTokenStorePort,
        mailer: EmailSenderPort,
        ttl_seconds: int,
        activation_base_url: str,
    ) -> None:
        """Build the use case.

        Args:
            create_user (CreateUserUseCase): Validates and persists the user.
            user_repo (UserRepositoryPort): Looked up by `resend_activation`.
            tokens (AccountTokenStorePort): Issues the single-use activation
                token (expected to be scoped to activation, not reset -
                see `main.py` wiring).
            mailer (EmailSenderPort): Sends the activation email.
            ttl_seconds (int): Activation link lifetime.
            activation_base_url (str): Public origin the link is built
                against (`{activation_base_url}/activate-account/{token}`) -
                must be where the PWA serves that route, not just the API.
        """
        self._create_user = create_user
        self._user_repo = user_repo
        self._tokens = tokens
        self._mailer = mailer
        self._ttl = ttl_seconds
        self._base_url = activation_base_url.rstrip("/")

    async def execute(
        self,
        *,
        email: str,
        name: str,
        role: str,
        tenant_ids: List[UUID],
    ) -> User:
        """Create the user (pending) and send their activation email.

        Args:
            email (str): Login email.
            name (str): Display name.
            role (str): One of `USER_ROLES`.
            tenant_ids (List[UUID]): Tenants to assign (see `CreateUserUseCase`).

        Returns:
            User: The created (pending) user.

        Raises:
            ValueError: On invalid input (see `CreateUserUseCase`).
            UserAlreadyExistsError: If the email is already registered.
            EmailSendError: If the activation email could not be sent. The
                user is NOT rolled back - it stays created and can be
                reached via `resend_activation`, rather than being silently
                lost to a provider hiccup.
        """
        random_password = secrets.token_urlsafe(_RANDOM_PASSWORD_LENGTH)
        user = await self._create_user.execute(
            email=email,
            name=name,
            role=role,
            password=random_password,
            tenant_ids=tenant_ids,
            status="pending",
        )
        await self._send_activation_email(user)
        return user

    async def resend_activation(self, user_id: UUID) -> bool:
        """Re-send the activation email for a user still `pending`.

        Args:
            user_id (UUID): The user to resend to.

        Returns:
            bool: True if an email was sent, False if the user does not
            exist or is no longer `pending` (already active/disabled).

        Raises:
            EmailSendError: If the email could not be sent.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.status != "pending":
            return False
        await self._send_activation_email(user)
        return True

    async def _send_activation_email(self, user: User) -> None:
        """Issue a fresh token and email the activation link.

        Args:
            user (User): Recipient; must currently be `pending`.
        """
        token = await self._tokens.issue(user.id, ttl_seconds=self._ttl)
        link = f"{self._base_url}/activate-account/{token}"
        await self._mailer.send_template(
            to=user.email,
            template="account_activation",
            context={"name": user.name, "link": link, "ttl_hours": self._ttl // 3600},
            subject="Activa tu cuenta en Flowsdone",
        )
