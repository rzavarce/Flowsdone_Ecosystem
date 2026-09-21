"""User domain model for the operator console (PWA) authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

UserRole = Literal["admin", "tenant_manager", "botmaster", "client"]

USER_ROLES: tuple[str, ...] = ("admin", "tenant_manager", "botmaster", "client")
"""All valid roles. `admin` sees every tenant; the rest are scoped to
the tenants listed in `User.tenant_ids`."""

UserStatus = Literal["active", "disabled"]


class User(BaseModel):
    """A person who signs in to the console.

    The password hash is intentionally NOT part of this model, so it
    cannot leak through serialization; see `UserCredentials`.

    Attributes:
        id (UUID): Unique identifier.
        email (str): Login identifier, always stored lowercase.
        name (str): Display name.
        role (UserRole): Access profile.
        status (UserStatus): `disabled` users cannot sign in and their
            live sessions stop working.
        tenant_ids (list[UUID]): Tenants this user is a member of. Ignored
            for `admin`, who has access to all of them.
        last_login_at (Optional[datetime]): Last successful sign-in.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    email: str
    name: str
    role: UserRole
    status: UserStatus = "active"
    tenant_ids: list[UUID] = Field(default_factory=list)
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @property
    def is_active(self) -> bool:
        """Whether the user may sign in and keep using live sessions."""
        return self.status == "active"


class UserCredentials(BaseModel):
    """A user together with the hash needed to verify a login attempt.

    Only returned by `UserRepositoryPort.get_credentials_by_email`; keep
    it inside the login use case.

    Attributes:
        user (User): The user.
        password_hash (str): Self-describing hash (see `PasswordHasherPort`).
    """

    user: User
    password_hash: str
