"""Contact: who is behind a conversation's channel identifier."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

# Fields a contact card holds, besides its identity.
CONTACT_FIELDS = ("name", "email", "phone", "username", "notes")


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
        username (Optional[str]): The person's account on the channel
            (an Instagram or Telegram @user), when it has one.
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
    username: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SenderProfile(BaseModel):
    """What a channel says about who sent a message, to start their card.

    Each channel gives something different: WhatsApp the number and the
    name on the account, Telegram the name and @user, Instagram the
    account, Facebook the name (looked up by the page); a web visitor only
    gets a generic name.

    Attributes:
        name (Optional[str]): Name to show.
        phone (Optional[str]): Phone number.
        username (Optional[str]): Account on the channel (@user).
    """

    name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None

    def fields(self) -> dict:
        """The non-empty fields, as contact card fields.

        Returns:
            dict: Field name -> value.
        """
        return {k: v for k, v in self.model_dump().items() if v}


def generic_contact_name(kind: str, visitor_id: str) -> str:
    """Name for a contact the channel knows nothing about (a web visitor).

    Same style as the demo page's browser calls ("client:demo-1890on91"),
    so staff recognise them and can rename them.

    Args:
        kind (str): Where they came from ("webchat", "demo").
        visitor_id (str): The visitor's browser id.

    Returns:
        str: "client:<kind>-<first 8 letters/digits of the id>".
    """
    return f"client:{kind}-{re.sub(r'[^a-z0-9]', '', visitor_id.lower())[:8]}"
