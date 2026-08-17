"""Project domain model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Project(BaseModel):
    """A project owned by a tenant.

    Attributes:
        id (UUID): Unique identifier.
        tenant_id (UUID): Id of the owning tenant.
        name (str): Display name.
        slug (str): Unique URL-safe identifier.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    tenant_id: UUID
    name: str
    slug: str
    status: str = "active"
    created_at: datetime
    updated_at: datetime
