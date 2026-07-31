from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Tenant(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str = "active"
    created_at: datetime
    updated_at: datetime
