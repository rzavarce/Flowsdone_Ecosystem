"""Records share link ("Share" button) chats as conversations of a "demo" channel.

Demo chats go straight to the agent's flow, without the Switchboard, so they
never reach the plan's quota. But staff want to see what prospects asked,
so each visitor of a share link gets a Session of its own, channel "demo",
and its messages are recorded through the same ConversationTracker as any
channel - with `billable=False`, so they are neither counted for the quota
nor billed as AI messages.

The Session's id is the one the chat's WebSocket is registered under
(`share:<link>:<visitor>`), which is also the conversation id the reply
comes back with: HandleOutboundResponseUseCase finds the Session by it and
records the agent's reply in the same conversation. A share link has no
channel connection; its id stands in for one (the "connection" the demo
messages came through), so the conversation schema needs no change.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.application.services.conversation_tracker import ConversationTracker
from app.domain.models.session import Session
from app.domain.ports.outbound import (
    ProjectRepositoryPort,
    SessionHistoryRepositoryPort,
    SessionRepositoryPort,
)

logger = logging.getLogger("conversations.demo")

# Conversation channel of share link chats, as listed in the console.
DEMO_CHANNEL = "demo"
_APP = "langflow"


class DemoConversationRecorder:
    """Records the visitor's messages of a share link chat."""

    def __init__(
        self,
        *,
        sessions: SessionRepositoryPort,
        history: SessionHistoryRepositoryPort,
        tracker: ConversationTracker,
        projects: ProjectRepositoryPort,
        session_ttl_seconds: int,
    ) -> None:
        """Build the recorder.

        Args:
            sessions (SessionRepositoryPort): Fast session state (Redis).
            history (SessionHistoryRepositoryPort): Durable transcript.
            tracker (ConversationTracker): Opens/rotates conversations and
                publishes each message to the archive.
            projects (ProjectRepositoryPort): To find the agent's tenant.
            session_ttl_seconds (int): Session TTL, like the Switchboard's.
        """
        self._sessions = sessions
        self._history = history
        self._tracker = tracker
        self._projects = projects
        self._ttl = session_ttl_seconds

    async def record_inbound(
        self,
        *,
        session_id: str,
        share_id: UUID,
        agent_id: UUID,
        project_id: UUID,
        visitor_id: str,
        text: str,
        now: datetime,
    ) -> None:
        """Record one message of a share link visitor. Never raises.

        A recording failure must not break the chat, so it is logged instead.

        Args:
            session_id (str): The chat's registry id (`share:<link>:<visitor>`).
            share_id (UUID): The share link.
            agent_id (UUID): The agent it opens.
            project_id (UUID): The agent's project.
            visitor_id (str): The visitor's browser id.
            text (str): What the visitor wrote.
            now (datetime): When (timezone-aware).
        """
        try:
            session = await self._sessions.get(session_id)
            if session is None:
                session = await self._new_session(session_id, share_id, agent_id, project_id, visitor_id, now)
                if session is None:
                    return
                await self._history.append_event(
                    session_id=session_id, project_id=project_id, event_type="started", to_app=_APP
                )
            await self._history.append_message(
                session_id=session_id, project_id=project_id, direction="inbound", text=text, app=_APP
            )
            session.record_message(direction="inbound", text=text, app=_APP, timestamp=now)
            await self._tracker.record_inbound(session=session, text=text, now=now, billable=False)
            await self._sessions.save(session, ttl_seconds=self._ttl)
        except Exception:
            logger.error("conversations.demo.record_failed", extra={"session_id": session_id}, exc_info=True)

    async def _new_session(
        self,
        session_id: str,
        share_id: UUID,
        agent_id: UUID,
        project_id: UUID,
        visitor_id: str,
        now: datetime,
    ) -> Optional[Session]:
        """A new "demo" Session for a share link visitor.

        Args:
            session_id (str): The chat's registry id.
            share_id (UUID): The share link (stands in for the channel connection).
            agent_id (UUID): The agent.
            project_id (UUID): Its project.
            visitor_id (str): The visitor's browser id.
            now (datetime): Current time.

        Returns:
            Optional[Session]: The session, or None if the project is gone.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            return None
        return Session(
            id=session_id,
            tenant_id=project.tenant_id,
            project_id=project_id,
            channel_type=DEMO_CHANNEL,
            channel_connection_id=share_id,
            agent_id=agent_id,
            external_conversation_key=visitor_id,
            # What the console shows as the contact: which demo visitor.
            user_identifier=f"Demo · visitante {visitor_id[:8]}",
            current_app=_APP,
            started_at=now,
            last_activity_at=now,
        )
