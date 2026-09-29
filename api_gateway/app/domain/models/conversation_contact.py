"""Contact: who is behind a conversation's channel identifier."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

# Fields a contact card holds, besides its identity.
CONTACT_FIELDS = ("name", "email", "phone", "notes")


class Contact(BaseModel):
    """The person behind a channel identifier, within one tenant.

    Conversations only know how a channel identifies someone (a phone
    number, an @user, a demo visitor id). A contact gives that identifier a
    name and details, shared by every conversation with the same identity,
    so staff see "Ana Pérez" instead of "+34600111222".

    Attributes:
        id (UUID): Contact id.
        tenant_id (UUID): Tenant it belongs to.
        channel_type (str): Channel the identifier is from.
        identifier (str): The channel's identifier (a conversation's `contact`).
        name (Optional[str]): Display name.
        email (Optional[str]): Email.
        phone (Optional[str]): Phone.
        notes (Optional[str]): Free notes.
        created_at (datetime): Creation time.
        updated_at (datetime): Last change.
    """

    id: UUID
    tenant_id: UUID
    channel_type: str
    identifier: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
