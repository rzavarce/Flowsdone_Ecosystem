"""Port for the durable, append-only conversation history (Postgres)."""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from api_gateway.app.domain.models.session import MessageDirection

SessionEventType = str
"""One of "started" / "app_switched" / "closed" - kept as a plain str
(not a Literal) at the port boundary so future event types don't force
a port signature change; adapters validate against the DB CHECK
constraint.
"""


class SessionHistoryRepositoryPort(Protocol):
    """Append-only audit trail of a conversation: every message turn and
    every switchboard-level lifecycle event (session started, app
    switched, session closed).

    Deliberately separate from SessionRepositoryPort (ISP): this is a
    write-mostly historical log for audit/analytics, not the live
    routing state Switchboard reads on every turn.
    """

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
        ...

    async def append_event(
        self,
        *,
        session_id: str,
        project_id: UUID,
        event_type: SessionEventType,
        from_app: Optional[str] = None,
        to_app: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Record a session lifecycle event.

        Args:
            session_id (str): Conversation id.
            project_id (UUID): Id of the owning project.
            event_type (SessionEventType): "started", "app_switched" or
                "closed".
            from_app (Optional[str]): Previous app, for "app_switched".
            to_app (Optional[str]): New/current app.
            reason (Optional[str]): Free-form reason, if any.
        """
        ...
