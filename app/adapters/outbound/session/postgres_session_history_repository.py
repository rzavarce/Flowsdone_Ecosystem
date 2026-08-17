"""SQLAlchemy implementation of SessionHistoryRepositoryPort."""

from __future__ import annotations

import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models.session import MessageDirection
from app.domain.ports.outbound import SessionHistoryRepositoryPort
from app.adapters.outbound.db.models import SessionEventModel, SessionMessageModel


class PostgresSessionHistoryRepository(SessionHistoryRepositoryPort):
    """Postgres-backed implementation of SessionHistoryRepositoryPort.

    Uses SQLAlchemy (not raw asyncpg like PostgresIdempotencyRepository)
    for consistency with every other repository the `api` process uses
    - Switchboard/HandleOutboundResponseUseCase.deliver() run in `api`,
    not inside a tight Kafka consumer loop, so the hot-path justification
    for raw asyncpg does not apply here.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def append_message(
        self,
        *,
        session_id: str,
        project_id: UUID,
        direction: MessageDirection,
        text: str,
        app: str,
    ) -> None:
        """Record one turn of the conversation.

        Args:
            session_id (str): Conversation id.
            project_id (UUID): Id of the owning project.
            direction (MessageDirection): "inbound" or "outbound".
            text (str): The message text.
            app (str): Which app produced/received this turn.
        """
        async with self._sessionmaker() as session:
            session.add(
                SessionMessageModel(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    project_id=project_id,
                    direction=direction,
                    app=app,
                    text=text,
                )
            )
            await session.commit()

    async def append_event(
        self,
        *,
        session_id: str,
        project_id: UUID,
        event_type: str,
        from_app: Optional[str] = None,
        to_app: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Record a session lifecycle event.

        Args:
            session_id (str): Conversation id.
            project_id (UUID): Id of the owning project.
            event_type (str): "started", "app_switched" or "closed".
            from_app (Optional[str]): Previous app, for "app_switched".
            to_app (Optional[str]): New/current app.
            reason (Optional[str]): Free-form reason, if any.
        """
        async with self._sessionmaker() as session:
            session.add(
                SessionEventModel(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    project_id=project_id,
                    event_type=event_type,
                    from_app=from_app,
                    to_app=to_app,
                    reason=reason,
                )
            )
            await session.commit()
