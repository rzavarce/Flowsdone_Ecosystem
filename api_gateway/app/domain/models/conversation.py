"""Conversation domain model: one bounded, billable exchange with a
contact, and the lifecycle policy that decides when it ends.

A Conversation is NOT the same thing as a Switchboard Session. The
Session id is deterministic per contact
(`{project_id}:{channel_type}:{external_conversation_key}`) and is
reused forever; a Conversation has its own UUID and is closed after a
period of inactivity (or a maximum duration), after which the next
inbound message opens a new one. Its UUID is also what Langflow uses
as `session_id`, so the bot's memory (and the LLM context sent on
every turn) is scoped to one conversation instead of growing forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

ConversationStatus = Literal["open", "closed"]
ConversationCloseReason = Literal["inactivity", "max_duration", "manual"]


class Conversation(BaseModel):
    """One conversation with a contact, from its first inbound message
    until it is closed.

    Attributes:
        id (UUID): Conversation id (also the Langflow/Langfuse session_id).
        session_id (str): Id of the Switchboard Session it belongs to.
        tenant_id (UUID): Id of the owning tenant.
        project_id (UUID): Id of the owning project.
        agent_id (UUID): Id of the agent that handles it.
        channel_type (str): Channel it happens on.
        channel_connection_id (UUID): Id of the matched channel connection.
        contact (str): Who is on the other end (phone number, username...).
        status (ConversationStatus): "open" or "closed".
        started_at (datetime): When the first inbound message arrived.
        last_inbound_at (datetime): When the contact last wrote - the
            inactivity window is measured from here, like WhatsApp's
            24h customer service window.
        last_message_at (datetime): When any message (either direction)
            was last recorded.
        inbound_count (int): Messages received from the contact.
        outbound_count (int): Messages sent to the contact.
        closed_at (Optional[datetime]): When it was closed.
        close_reason (Optional[ConversationCloseReason]): Why it was closed.
    """

    id: UUID
    session_id: str
    tenant_id: UUID
    project_id: UUID
    agent_id: UUID
    channel_type: str
    channel_connection_id: UUID
    contact: str
    status: ConversationStatus = "open"
    started_at: datetime
    last_inbound_at: datetime
    last_message_at: datetime
    inbound_count: int = 0
    outbound_count: int = 0
    closed_at: Optional[datetime] = None
    close_reason: Optional[ConversationCloseReason] = None


@dataclass(frozen=True)
class ConversationExpiry:
    """When and why an open conversation stops being current.

    Attributes:
        at (datetime): The moment the conversation expires.
        reason (ConversationCloseReason): Which limit is hit first.
    """

    at: datetime
    reason: ConversationCloseReason


@dataclass(frozen=True)
class ConversationLifecyclePolicy:
    """Decides when an open conversation ends.

    A conversation ends at whichever comes first: `inactivity` after
    the contact's last message, or `max_duration` after it started -
    the latter keeps a very chatty contact from growing one
    conversation (and its LLM context) without bound.

    Attributes:
        inactivity (timedelta): Idle window measured from the contact's
            last inbound message.
        max_duration (timedelta): Hard cap measured from the start.
    """

    inactivity: timedelta
    max_duration: timedelta

    def expiry(self, conversation: Conversation) -> ConversationExpiry:
        """Compute when (and why) a conversation expires.

        Args:
            conversation (Conversation): The conversation to evaluate.

        Returns:
            ConversationExpiry: The earliest limit it hits.
        """
        by_inactivity = conversation.last_inbound_at + self.inactivity
        by_duration = conversation.started_at + self.max_duration
        if by_duration <= by_inactivity:
            return ConversationExpiry(at=by_duration, reason="max_duration")
        return ConversationExpiry(at=by_inactivity, reason="inactivity")

    def is_expired(self, conversation: Conversation, now: datetime) -> bool:
        """Tell whether a conversation is no longer current at `now`.

        Args:
            conversation (Conversation): The conversation to evaluate.
            now (datetime): The current time (timezone-aware).

        Returns:
            bool: True if it is closed, or open but past its expiry.
        """
        if conversation.status == "closed":
            return True
        return now >= self.expiry(conversation).at
