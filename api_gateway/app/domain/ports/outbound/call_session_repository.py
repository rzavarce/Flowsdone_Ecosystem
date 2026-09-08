"""Port for persisting ephemeral voice call session state."""

from __future__ import annotations

from typing import Optional, Protocol

from app.domain.models.call_session import CallSession


class CallSessionRepositoryPort(Protocol):
    """Ephemeral (TTL-backed) storage for CallSession.

    A call's TwiML-equivalent webhook and its streaming WebSocket
    arrive as two separate requests that do not share process memory,
    so the session built on the first request must be persisted
    somewhere both can reach - unlike WSRegistry (in-process, holds
    the live WebSocket object itself), this only holds the small,
    serializable context needed to resume handling the call.
    """

    async def save(self, session: CallSession, *, ttl_seconds: int) -> None:
        """Persist a call session, expiring it after `ttl_seconds`.

        Args:
            session (CallSession): The call session to store.
            ttl_seconds (int): Seconds after which the entry expires,
                as an upper bound on call duration.
        """
        ...

    async def get(self, call_sid: str) -> Optional[CallSession]:
        """Fetch a call session by its call_sid.

        Args:
            call_sid (str): Provider-assigned unique id for the call.

        Returns:
            Optional[CallSession]: The call session, or None if it does
            not exist or has expired.
        """
        ...

    async def delete(self, call_sid: str) -> None:
        """Remove a call session.

        Args:
            call_sid (str): Provider-assigned unique id for the call.
        """
        ...
