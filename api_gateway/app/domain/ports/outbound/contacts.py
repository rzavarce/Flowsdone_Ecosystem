"""Port for contacts (the person behind a conversation's identifier)."""

from __future__ import annotations

from typing import Any, Collection, Dict, Iterable, List, Optional, Protocol, Tuple
from uuid import UUID

from app.domain.models.conversation_contact import Contact, ContactSummary, SenderProfile

# (tenant_id, channel_type, identifier): what identifies a contact.
ContactKey = Tuple[UUID, str, str]


class ContactRepositoryPort(Protocol):
    """Persistence of contacts, one per tenant, channel and identifier."""

    async def get(self, key: ContactKey) -> Optional[Contact]:
        """One contact.

        Args:
            key (ContactKey): Its identity.

        Returns:
            Optional[Contact]: The contact, or None if nobody named it yet.
        """
        ...

    async def find_many(self, keys: Iterable[ContactKey]) -> Dict[ContactKey, Contact]:
        """Several contacts at once (e.g. for a page of conversations).

        Args:
            keys (Iterable[ContactKey]): Identities to look up.

        Returns:
            Dict[ContactKey, Contact]: The ones that exist.
        """
        ...

    async def upsert(self, key: ContactKey, fields: Dict[str, Optional[str]], *, only_empty: bool = False) -> Contact:
        """Create the contact or update its fields.

        Args:
            key (ContactKey): Its identity.
            fields (Dict[str, Optional[str]]): Fields to set (a subset of
                name, email, phone, notes); None clears a field.
            only_empty (bool): Only fill fields that are still empty, never
                overwrite (for details an agent captured: staff edits win).

        Returns:
            Contact: The contact as stored.
        """
        ...


    async def get_by_id(self, contact_id: UUID) -> Optional[Contact]:
        """One contact by its id.

        Args:
            contact_id (UUID): Contact id.

        Returns:
            Optional[Contact]: The contact, or None.
        """
        ...

    async def search(
        self,
        *,
        tenant_ids: Optional[Collection[UUID]],
        query: Optional[str] = None,
        channel_type: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
    ) -> List[ContactSummary]:
        """Contacts for the contact list, most recent activity first.

        Args:
            tenant_ids (Optional[Collection[UUID]]): Only these tenants; None = all.
            query (Optional[str]): Name, email, phone, @user or identifier
                contains this text (case-insensitive).
            channel_type (Optional[str]): Only this channel.
            limit (int): Page size.
            offset (int): Items to skip.

        Returns:
            List[ContactSummary]: The page.
        """
        ...


class SenderProfileLookupPort(Protocol):
    """Asks a channel who sent a message, for channels whose webhook only
    carries an opaque id (Facebook's PSID, Instagram's IGSID)."""

    async def lookup(
        self, *, channel_type: str, sender_id: str, credentials: Dict[str, Any]
    ) -> Optional[SenderProfile]:
        """The sender's profile, best-effort.

        Args:
            channel_type (str): The channel.
            sender_id (str): The channel's id of the sender.
            credentials (Dict[str, Any]): The channel connection's credentials.

        Returns:
            Optional[SenderProfile]: What the channel told, or None if the
            channel has no lookup or it failed (never raises).
        """
        ...
