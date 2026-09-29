"""Port for contacts (the person behind a conversation's identifier)."""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Protocol, Tuple
from uuid import UUID

from app.domain.models.conversation_contact import Contact

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
