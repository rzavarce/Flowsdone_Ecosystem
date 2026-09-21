"""DTOs returned by the console authentication use cases."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.domain.models.user import UserRole


class TenantRef(BaseModel):
    """Minimal tenant reference shown to a signed-in user.

    Attributes:
        id (UUID): Tenant id.
        name (str): Tenant display name.
    """

    id: UUID
    name: str


class AuthenticatedUser(BaseModel):
    """The signed-in user as the console needs it.

    Attributes:
        id (UUID): User id.
        email (str): Login email.
        name (str): Display name.
        role (UserRole): Access profile.
        tenants (list[TenantRef]): Tenants the user can work on. For an
            `admin` this is every tenant.
    """

    id: UUID
    email: str
    name: str
    role: UserRole
    tenants: list[TenantRef]
