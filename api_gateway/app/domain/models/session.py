"""Conversation session domain model — the state Switchboard reads and
writes to decide/remember which app is handling a conversation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

SessionStatus = Literal["active", "closed"]
MessageDirection = Literal["inbound", "outbound"]

# Bound on Session.last_messages - a fast, in-Redis rolling window for
# cheap context; the full transcript lives in Postgres
# (SessionHistoryRepositoryPort), not here.
LAST_MESSAGES_LIMIT = 10


class SessionMessage(BaseModel):
    """One turn of the conversation, as kept in the session's fast,
    bounded in-Redis window (see LAST_MESSAGES_LIMIT).

    Attributes:
        direction (MessageDirection): Whether the caller/user sent it
            ("inbound") or an app replied with it ("outbound").
        text (str): The message text.
        app (str): Which app produced/received this turn (matches
            AppConnectorPort.app_name at the time).
        timestamp (datetime): When the turn happened.
    """

    direction: MessageDirection
    text: str
    app: str
    timestamp: datetime


class Session(BaseModel):
    """Persisted state of one conversation, across however many turns
    and app switches it goes through.

    `id` is the same deterministic string every channel has always used
    as `conversation_id` (`f"{project_id}:{channel_type}:{external_conversation_key}"`)
    - kept identical on purpose so Langflow's own session memory (keyed
    by that same string, see LangflowExecutorPort) is never fragmented
    by this feature.

    Attributes:
        id (str): Conversation id (see above).
        tenant_id (UUID): Id of the owning tenant.
        project_id (UUID): Id of the owning project.
        channel_type (str): Which channel this conversation is on.
        channel_connection_id (UUID): Id of the matched channel connection.
        agent_id (UUID): Id of the agent that owns this conversation
            (stable platform identity, independent of which app is
            currently handling it).
        external_conversation_key (str): Id of the sender on the
            external platform (remoteJid/psid/chat_id/call_sid/...).
        user_identifier (str): Who is on the other end (phone number,
            username, etc.) - the "número o usuario de entrada".
        current_app (str): Which AppConnectorPort.app_name is currently
            handling this conversation.
        variables (Dict[str, Any]): Free-form session-scoped state a
            connector can read/write across turns - e.g. Langflow's
            connector snapshots the agent's langflow_flow_id here at
            session-creation time, so it stays fixed for the life of
            the conversation even if the agent's config changes later.
        last_messages (List[SessionMessage]): Bounded rolling window of
            the most recent turns (see LAST_MESSAGES_LIMIT).
        started_at (datetime): When the session was first created.
        last_activity_at (datetime): When the session last saw a turn.
        status (SessionStatus): Lifecycle state.
    """

    id: str
    tenant_id: UUID
    project_id: UUID
    channel_type: str
    channel_connection_id: UUID
    agent_id: UUID
    external_conversation_key: str
    user_identifier: str
    current_app: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    last_messages: List[SessionMessage] = Field(default_factory=list)
    started_at: datetime
    last_activity_at: datetime
    status: SessionStatus = "active"

    def record_message(self, *, direction: MessageDirection, text: str, app: str, timestamp: datetime) -> None:
        """Append a turn to the bounded rolling window and touch activity.

        Args:
            direction (MessageDirection): "inbound" or "outbound".
            text (str): The message text.
            app (str): Which app produced/received this turn.
            timestamp (datetime): When the turn happened.
        """
        self.last_messages.append(
            SessionMessage(direction=direction, text=text, app=app, timestamp=timestamp)
        )
        del self.last_messages[:-LAST_MESSAGES_LIMIT]
        self.last_activity_at = timestamp
