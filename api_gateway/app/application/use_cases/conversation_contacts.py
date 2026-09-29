"""Use case for contact cards: give a name (and email, phone, notes) to the
person behind a conversation's identifier.

A card belongs to a tenant, a channel and the identifier that channel gives
the person (the conversation's `contact`), so every conversation with the
same person shows the same name. The gateway starts it with the first
message, from what the channel says about the sender (number, name,
@user) and the details the person gives in the chat (email, or a name or
phone the agent asked for), only where the card is still empty; staff
edit it from a conversation, and what they type always wins.
"""

from __future__ import annotations

import re
from typing import Collection, Dict, Iterable, List, Optional
from uuid import UUID

from app.domain.models.conversation import Conversation
from app.application.services.contact_extraction import extract_contact_details
from app.domain.models.conversation_contact import CONTACT_FIELDS, Contact, ContactSummary, SenderProfile
from app.domain.ports.outbound import ContactKey, ContactRepositoryPort

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_LENGTH = {"name": 120, "email": 254, "phone": 40, "username": 120, "notes": 2000}


class InvalidContactError(ValueError):
    """A contact field has an invalid value (maps to 422)."""


def contact_key(conversation: Conversation) -> ContactKey:
    """The identity of a conversation's contact.

    Args:
        conversation (Conversation): The conversation.

    Returns:
        ContactKey: (tenant_id, channel_type, identifier).
    """
    return (conversation.tenant_id, conversation.channel_type, conversation.contact)


def _clean(fields: Dict[str, Optional[str]], *, drop_empty: bool) -> Dict[str, Optional[str]]:
    """Trim and validate contact fields.

    Args:
        fields (Dict[str, Optional[str]]): Raw fields (unknown keys ignored).
        drop_empty (bool): Leave out empty values (an agent sending "" means
            "don't know", not "clear it").

    Returns:
        Dict[str, Optional[str]]: The fields to store; an empty one becomes None.

    Raises:
        InvalidContactError: If a value is too long or the email is not one.
    """
    cleaned: Dict[str, Optional[str]] = {}
    for name in CONTACT_FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        value = " ".join(value.split()) if isinstance(value, str) and name != "notes" else value
        value = value.strip() if isinstance(value, str) else value
        if not value:
            if not drop_empty:
                cleaned[name] = None
            continue
        if len(value) > _MAX_LENGTH[name]:
            raise InvalidContactError(f"{name} is too long")
        if name == "email":
            value = value.lower()
            if not _EMAIL.match(value):
                raise InvalidContactError("email is not valid")
        cleaned[name] = value
    return cleaned


class ManageConversationContactsUseCase:
    """Reads and updates the contact cards of conversations."""

    def __init__(self, *, contacts: ContactRepositoryPort) -> None:
        """Build the use case.

        Args:
            contacts (ContactRepositoryPort): Contact cards.
        """
        self._contacts = contacts

    async def for_conversations(self, conversations: Iterable[Conversation]) -> Dict[UUID, Contact]:
        """The cards of a page of conversations.

        Args:
            conversations (Iterable[Conversation]): The conversations.

        Returns:
            Dict[UUID, Contact]: Conversation id -> its contact's card, for
            those whose contact has one.
        """
        items: List[Conversation] = list(conversations)
        found = await self._contacts.find_many(contact_key(c) for c in items)
        return {c.id: found[contact_key(c)] for c in items if contact_key(c) in found}

    async def update(self, conversation: Conversation, fields: Dict[str, Optional[str]]) -> Contact:
        """Staff edit a conversation's contact card (overwrites).

        Args:
            conversation (Conversation): The conversation.
            fields (Dict[str, Optional[str]]): Fields to set; empty clears one.

        Returns:
            Contact: The card as stored.

        Raises:
            InvalidContactError: If a value is invalid.
        """
        return await self._contacts.upsert(contact_key(conversation), _clean(fields, drop_empty=False))

    async def update_contact(self, contact: Contact, fields: Dict[str, Optional[str]]) -> Contact:
        """Staff edit a contact's card from the contact list (overwrites).

        Args:
            contact (Contact): The contact.
            fields (Dict[str, Optional[str]]): Fields to set; empty clears one.

        Returns:
            Contact: The card as stored.

        Raises:
            InvalidContactError: If a value is invalid.
        """
        key = (contact.tenant_id, contact.channel_type, contact.identifier)
        return await self._contacts.upsert(key, _clean(fields, drop_empty=False))

    async def get(self, contact_id: UUID) -> Optional[Contact]:
        """One contact by its id.

        Args:
            contact_id (UUID): Contact id.

        Returns:
            Optional[Contact]: The contact, or None.
        """
        return await self._contacts.get_by_id(contact_id)

    async def search(
        self,
        *,
        tenant_ids: Optional[Collection[UUID]],
        query: Optional[str] = None,
        channel_type: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
    ) -> List[ContactSummary]:
        """The contact list, most recent activity first.

        Args:
            tenant_ids (Optional[Collection[UUID]]): Only these tenants; None = all.
            query (Optional[str]): Text to look for (name, email, phone,
                @user or identifier).
            channel_type (Optional[str]): Only this channel.
            limit (int): Page size.
            offset (int): Items to skip.

        Returns:
            List[ContactSummary]: The page.
        """
        return await self._contacts.search(
            tenant_ids=tenant_ids, query=(query or "").strip() or None, channel_type=channel_type, limit=limit, offset=offset
        )

    async def record_from_channel(
        self,
        key: ContactKey,
        *,
        profile: Optional[SenderProfile] = None,
        text: str = "",
        asked: Optional[str] = None,
    ) -> Optional[Contact]:
        """Start or complete a contact's card from an inbound message.

        Uses what the channel says about the sender (`profile`) and the
        details found in the message itself (an email, or a name/phone the
        agent had just asked for). Only fills fields the card doesn't have
        yet: what staff typed, or what was found before, always stays.

        Args:
            key (ContactKey): The conversation's contact identity.
            profile (Optional[SenderProfile]): What the channel says.
            text (str): The message.
            asked (Optional[str]): The agent's previous message.

        Returns:
            Optional[Contact]: The card, or None if there was nothing to
            record (no call to the store then).
        """
        fields: Dict[str, Optional[str]] = dict(profile.fields()) if profile else {}
        for name, value in extract_contact_details(text, asked).items():
            fields.setdefault(name, value)
        try:
            cleaned = _clean(fields, drop_empty=True)
        except InvalidContactError:
            # A channel value out of bounds (a huge display name): keep the rest.
            cleaned = {}
            for name, value in fields.items():
                try:
                    cleaned.update(_clean({name: value}, drop_empty=True))
                except InvalidContactError:
                    continue
        if not cleaned:
            return None
        return await self._contacts.upsert(key, cleaned, only_empty=True)
