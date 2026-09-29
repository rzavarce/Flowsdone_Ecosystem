"""SQLAlchemy implementation of ContactRepositoryPort (contact cards)."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.models import ConversationContactModel
from app.domain.models.conversation_contact import CONTACT_FIELDS, Contact
from app.domain.ports.outbound import ContactKey, ContactRepositoryPort


def _to_domain(model: ConversationContactModel) -> Contact:
    """Convert a row into a Contact.

    Args:
        model (ConversationContactModel): The ORM row.

    Returns:
        Contact: The domain object.
    """
    return Contact(
        id=model.id,
        tenant_id=model.tenant_id,
        channel_type=model.channel_type,
        identifier=model.identifier,
        name=model.name,
        email=model.email,
        phone=model.phone,
        username=model.username,
        notes=model.notes,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyContactRepository(ContactRepositoryPort):
    """Postgres-backed contact cards."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def get(self, key: ContactKey) -> Optional[Contact]:
        """One contact.

        Args:
            key (ContactKey): (tenant_id, channel_type, identifier).

        Returns:
            Optional[Contact]: The contact, or None.
        """
        found = await self.find_many([key])
        return found.get(key)

    async def find_many(self, keys: Iterable[ContactKey]) -> Dict[ContactKey, Contact]:
        """Several contacts at once.

        Args:
            keys (Iterable[ContactKey]): Identities to look up.

        Returns:
            Dict[ContactKey, Contact]: The ones that exist.
        """
        wanted = list(dict.fromkeys(keys))
        if not wanted:
            return {}
        condition = or_(
            *(
                and_(
                    ConversationContactModel.tenant_id == tenant_id,
                    ConversationContactModel.channel_type == channel_type,
                    ConversationContactModel.identifier == identifier,
                )
                for tenant_id, channel_type, identifier in wanted
            )
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(select(ConversationContactModel).where(condition))).scalars()
            contacts = [_to_domain(row) for row in rows]
        return {(c.tenant_id, c.channel_type, c.identifier): c for c in contacts}

    async def upsert(self, key: ContactKey, fields: Dict[str, Optional[str]], *, only_empty: bool = False) -> Contact:
        """Create the contact or update its fields, in one statement.

        Args:
            key (ContactKey): (tenant_id, channel_type, identifier).
            fields (Dict[str, Optional[str]]): Fields to set; None clears one.
            only_empty (bool): Only fill fields that are still empty.

        Returns:
            Contact: The contact as stored.
        """
        tenant_id, channel_type, identifier = key
        values = {name: fields[name] for name in CONTACT_FIELDS if name in fields}
        stmt = insert(ConversationContactModel).values(
            tenant_id=tenant_id, channel_type=channel_type, identifier=identifier, **values
        )
        if only_empty:
            # A value already there (typed by staff, or captured before) wins.
            updates = {name: func.coalesce(getattr(ConversationContactModel, name), stmt.excluded[name]) for name in values}
        else:
            updates = {name: stmt.excluded[name] for name in values}
        updates["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(constraint="uq_contacts_identity", set_=updates).returning(ConversationContactModel)
        async with self._sessionmaker() as session:
            row = (await session.execute(stmt)).scalar_one()
            await session.commit()
            return _to_domain(row)
