"""Port for the fast, TTL-backed conversation session state."""

from __future__ import annotations

from typing import Optional, Protocol

from app.domain.models.session import Session


class SessionRepositoryPort(Protocol):
    """Fast (Redis-backed) storage for the live Session, read/written on
    every turn by Switchboard - the durable, append-only transcript
    lives separately, in SessionHistoryRepositoryPort.
    """

    async def get(self, session_id: str) -> Optional[Session]:
        """Fetch a session by id.

        Args:
            session_id (str): Conversation id.

        Returns:
            Optional[Session]: The session, or None if it does not
            exist or has expired.
        """
        ...

    async def save(self, session: Session, *, ttl_seconds: int) -> None:
        """Persist a session, expiring it after `ttl_seconds` of inactivity.

        Args:
            session (Session): The session to store.
            ttl_seconds (int): Seconds after which the entry expires if
                untouched.
        """
        ...

    async def delete(self, session_id: str) -> None:
        """Remove a session.

        Args:
            session_id (str): Conversation id.
        """
        ...
