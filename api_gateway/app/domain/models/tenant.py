"""Tenant domain model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Tenant(BaseModel):
    """A top-level tenant in the multi-tenant SaaS.

    Attributes:
        id (UUID): Unique identifier.
        name (str): Display name.
        slug (str): Unique URL-safe identifier.
        status (str): Lifecycle status (e.g. "active").
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID
    name: str
    slug: str
    status: str = "active"
    created_at: datetime
    updated_at: datetime
