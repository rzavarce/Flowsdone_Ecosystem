"""Use case: create a console user."""

from __future__ import annotations

import asyncio
import re
from typing import List
from uuid import UUID

from app.domain.models.user import USER_ROLES, User
from app.domain.ports.outbound import PasswordHasherPort, TenantRepositoryPort, UserRepositoryPort

__all__ = ["CreateUserUseCase", "MIN_PASSWORD_LENGTH"]

MIN_PASSWORD_LENGTH = 10
# Deliberately loose: real validation is "can they receive mail"; this only
# rejects obvious typos.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateUserUseCase:
    """Validates and creates a user with a hashed password.

    Raises `ValueError` (with a message meant for the operator) on invalid
    input, and `UserAlreadyExistsError` if the email is taken.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        hasher: PasswordHasherPort,
    ) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Persists the user.
            tenant_repo (TenantRepositoryPort): Validates tenant ids.
            hasher (PasswordHasherPort): Hashes the password.
        """
        self._user_repo = user_repo
        self._tenant_repo = tenant_repo
        self._hasher = hasher

    async def execute(
        self,
        *,
        email: str,
        name: str,
        role: str,
        password: str,
        tenant_ids: List[UUID],
    ) -> User:
        """Create a user.

        Args:
            email (str): Login email (stored lowercase).
            name (str): Display name.
            role (str): One of `USER_ROLES`.
            password (str): Plaintext password (min `MIN_PASSWORD_LENGTH`).
            tenant_ids (List[UUID]): Tenants to assign. Required for every
                role except `admin`, who sees all tenants.

        Returns:
            User: The created user.

        Raises:
            ValueError: On invalid email, name, role, password or tenants.
            UserAlreadyExistsError: If the email is already registered.
        """
        email = email.strip().lower()
        name = name.strip()
        if not _EMAIL_RE.match(email):
            raise ValueError("invalid email")
        if not name:
            raise ValueError("name is required")
        if role not in USER_ROLES:
            raise ValueError(f"role must be one of: {', '.join(USER_ROLES)}")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

        if role == "admin":
            tenant_ids = []  # admins see every tenant; memberships would be noise
        else:
            if not tenant_ids:
                raise ValueError(f"role '{role}' needs at least one tenant")
            found = {t.id for t in await self._tenant_repo.list_by_ids(tenant_ids)}
            missing = [str(t) for t in tenant_ids if t not in found]
            if missing:
                raise ValueError(f"unknown tenant id(s): {', '.join(missing)}")

        password_hash = await asyncio.to_thread(self._hasher.hash, password)
        return await self._user_repo.create(
            email=email,
            name=name,
            role=role,
            password_hash=password_hash,
            tenant_ids=tenant_ids,
        )
