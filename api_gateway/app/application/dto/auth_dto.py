"""DTOs returned by the console authentication use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
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
        phone (Optional[str]): Optional contact phone.
        address (Optional[str]): Optional postal address.
        social_links (Dict[str, str]): Optional profile links by network.
        avatar_updated_at (Optional[datetime]): Set when the user has a
            photo (served by `GET /me/avatar`); doubles as a cache-buster.
    """

    id: UUID
    email: str
    name: str
    role: UserRole
    tenants: list[TenantRef]
    phone: Optional[str] = None
    address: Optional[str] = None
    social_links: Dict[str, str] = {}
    avatar_updated_at: Optional[datetime] = None
