"""SQLAlchemy implementation of ConversationRepositoryPort."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.models import ConversationModel
from app.domain.models.conversation import Conversation, ConversationCloseReason
from app.domain.models.session import MessageDirection
from app.domain.ports.outbound import ConversationRepositoryPort

# Closes a batch of expired conversations in one statement. closed_at is
# the moment each one actually expired (the earliest of its two limits),
# not the time the sweep happened to run; the tie-break (max_duration
# wins) matches ConversationLifecyclePolicy.expiry(). SKIP LOCKED lets
# several sweepers run at once without closing the same rows twice.
_CLOSE_EXPIRED_SQL = text(
    """
    WITH expired AS (
        SELECT id FROM conversations
        WHERE status = 'open'
          AND (last_inbound_at <= :inactive_before OR started_at <= :started_before)
        ORDER BY last_inbound_at
        LIMIT :limit
        FOR UPDATE SKIP LOCKED
    )
    UPDATE conversations AS c
    SET status = 'closed',
        closed_at = LEAST(c.last_inbound_at + :inactivity, c.started_at + :max_duration),
        close_reason = CASE
            WHEN c.started_at + :max_duration <= c.last_inbound_at + :inactivity THEN 'max_duration'
            ELSE 'inactivity'
        END
    FROM expired
    WHERE c.id = expired.id
    RETURNING c.*
    """
)


def _to_domain(model: ConversationModel) -> Conversation:
    """Convert a ConversationModel row (or a row with the same columns)
    into a domain object.

    Args:
        model (ConversationModel): The ORM row or result row to convert.

    Returns:
        Conversation: The equivalent domain object.
    """
    return Conversation(
        id=model.id,
        session_id=model.session_id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        channel_type=model.channel_type,
        channel_connection_id=model.channel_connection_id,
        contact=model.contact,
        status=model.status,
        started_at=model.started_at,
        last_inbound_at=model.last_inbound_at,
        last_message_at=model.last_message_at,
        inbound_count=model.inbound_count,
        outbound_count=model.outbound_count,
        closed_at=model.closed_at,
        close_reason=model.close_reason,
    )


class SqlAlchemyConversationRepository(ConversationRepositoryPort):
    """Postgres-backed implementation of ConversationRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def get(self, conversation_id: UUID) -> Optional[Conversation]:
        """Fetch a conversation by id.

        Args:
            conversation_id (UUID): Conversation id.

        Returns:
            Optional[Conversation]: The conversation, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(ConversationModel, conversation_id)
            return _to_domain(model) if model else None

    async def open(self, conversation: Conversation) -> Conversation:
        """Store a new open conversation, or return the one already open
        for the same session (enforced by the partial unique index
        uq_conversations_open_session).

        Args:
            conversation (Conversation): The conversation to open.

        Returns:
            Conversation: The stored open conversation.
        """
        values = conversation.model_dump(exclude={"closed_at", "close_reason"})
        values["status"] = "open"
        statement = (
            insert(ConversationModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["session_id"], index_where=text("status = 'open'"))
            .returning(ConversationModel)
        )
        async with self._sessionmaker() as session:
            inserted = (await session.execute(statement)).scalar_one_or_none()
            if inserted is None:
                inserted = (
                    await session.execute(
                        select(ConversationModel).where(
                            ConversationModel.session_id == conversation.session_id,
                            ConversationModel.status == "open",
                        )
                    )
                ).scalar_one()
            await session.commit()
            return _to_domain(inserted)

    async def record_message(
        self, conversation_id: UUID, *, direction: MessageDirection, at: datetime
    ) -> None:
        """Bump the counters/timestamps of a conversation for one message.
        Timestamps only move forward, so out-of-order calls are harmless.

        Args:
            conversation_id (UUID): Conversation id.
            direction (MessageDirection): "inbound" or "outbound".
            at (datetime): When the message happened.
        """
        values = {"last_message_at": func.greatest(ConversationModel.last_message_at, at)}
        if direction == "inbound":
            values["inbound_count"] = ConversationModel.inbound_count + 1
            values["last_inbound_at"] = func.greatest(ConversationModel.last_inbound_at, at)
        else:
            values["outbound_count"] = ConversationModel.outbound_count + 1

        async with self._sessionmaker() as session:
            await session.execute(
                update(ConversationModel).where(ConversationModel.id == conversation_id).values(**values)
            )
            await session.commit()

    async def close(
        self, conversation_id: UUID, *, reason: ConversationCloseReason, closed_at: datetime
    ) -> bool:
        """Close a conversation if it is still open.

        Args:
            conversation_id (UUID): Conversation id.
            reason (ConversationCloseReason): Why it is closed.
            closed_at (datetime): When it ended.

        Returns:
            bool: True if it was open and got closed.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                update(ConversationModel)
                .where(ConversationModel.id == conversation_id, ConversationModel.status == "open")
                .values(status="closed", closed_at=closed_at, close_reason=reason)
            )
            await session.commit()
            return result.rowcount > 0

    async def close_expired(
        self, *, now: datetime, inactivity: timedelta, max_duration: timedelta, limit: int
    ) -> List[Conversation]:
        """Close open conversations past either limit, in one statement.

        Args:
            now (datetime): The current time.
            inactivity (timedelta): Idle window after the last inbound message.
            max_duration (timedelta): Hard cap after the start.
            limit (int): Maximum number of conversations to close.

        Returns:
            List[Conversation]: The conversations that were closed.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                _CLOSE_EXPIRED_SQL,
                {
                    "inactive_before": now - inactivity,
                    "started_before": now - max_duration,
                    "inactivity": inactivity,
                    "max_duration": max_duration,
                    "limit": limit,
                },
            )
            rows = result.mappings().all()
            await session.commit()
            return [Conversation.model_validate(dict(row)) for row in rows]
