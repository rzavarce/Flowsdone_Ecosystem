"""Use case for contact cards: give a name (and email, phone, notes) to the
person behind a conversation's identifier.

A card belongs to a tenant, a channel and the identifier that channel gives
the person (the conversation's `contact`), so every conversation with the
same person shows the same name. Staff edit it from a conversation; an
agent can fill it in as it learns the details (see the "Guardar contacto"
Langflow component), but only where the card is still empty: what staff
typed always wins.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from app.domain.models.conversation import Conversation
from app.domain.models.conversation_contact import CONTACT_FIELDS, Contact
from app.domain.ports.outbound import ContactKey, ContactRepositoryPort, ConversationRepositoryPort

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_LENGTH = {"name": 120, "email": 254, "phone": 40, "notes": 2000}


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

    def __init__(self, *, contacts: ContactRepositoryPort, conversations: ConversationRepositoryPort) -> None:
        """Build the use case.

        Args:
            contacts (ContactRepositoryPort): Contact cards.
            conversations (ConversationRepositoryPort): To find a conversation
                an agent is talking in.
        """
        self._contacts = contacts
        self._conversations = conversations

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

    async def capture(self, conversation_id: UUID, fields: Dict[str, Optional[str]]) -> Optional[Contact]:
        """An agent tells what it learned about the contact of its conversation.

        Only fills what the card doesn't have yet, so a name staff typed is
        never replaced by a (maybe misheard) one.

        Args:
            conversation_id (UUID): The conversation the agent is in.
            fields (Dict[str, Optional[str]]): What it learned.

        Returns:
            Optional[Contact]: The card, or None if the conversation doesn't exist.

        Raises:
            InvalidContactError: If a value is invalid.
        """
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            return None
        cleaned = _clean(fields, drop_empty=True)
        if not cleaned:
            return await self._contacts.get(contact_key(conversation))
        return await self._contacts.upsert(contact_key(conversation), cleaned, only_empty=True)
