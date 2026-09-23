"""Ports for conversation tracking: the live conversation record
(Postgres), the message event stream (Kafka) and the long-term message
archive (ClickHouse).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Protocol, Sequence
from uuid import UUID

from app.domain.models.conversation import Conversation, ConversationCloseReason
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.models.session import MessageDirection


class ConversationRepositoryPort(Protocol):
    """Mutable, queryable state of each conversation (status, counters,
    timestamps) - what an inbox lists and filters. The message bodies
    themselves live in MessageArchivePort, not here.
    """

    async def get(self, conversation_id: UUID) -> Optional[Conversation]:
        """Fetch a conversation by id.

        Args:
            conversation_id (UUID): Conversation id.

        Returns:
            Optional[Conversation]: The conversation, or None.
        """
        ...

    async def open(self, conversation: Conversation) -> Conversation:
        """Store a new open conversation, unless its session already has
        one open - then return that one instead.

        At most one conversation per session can be open at a time, so
        two concurrent first messages of a contact never split into two
        conversations.

        Args:
            conversation (Conversation): The conversation to open.

        Returns:
            Conversation: The stored open conversation (the given one,
            or the one that was already open for its session).
        """
        ...

    async def record_message(
        self, conversation_id: UUID, *, direction: MessageDirection, at: datetime
    ) -> None:
        """Bump the counters/timestamps of a conversation for one message.

        Args:
            conversation_id (UUID): Conversation id.
            direction (MessageDirection): "inbound" or "outbound".
            at (datetime): When the message happened.
        """
        ...

    async def close(
        self, conversation_id: UUID, *, reason: ConversationCloseReason, closed_at: datetime
    ) -> bool:
        """Close a conversation if it is still open.

        Args:
            conversation_id (UUID): Conversation id.
            reason (ConversationCloseReason): Why it is closed.
            closed_at (datetime): When it ended.

        Returns:
            bool: True if it was open and got closed; False if it was
            already closed or does not exist.
        """
        ...

    async def close_expired(
        self, *, now: datetime, inactivity: timedelta, max_duration: timedelta, limit: int
    ) -> List[Conversation]:
        """Close open conversations past their inactivity window or
        maximum duration, stamping each with the moment it actually
        expired (not `now`).

        Args:
            now (datetime): The current time.
            inactivity (timedelta): Idle window after the last inbound message.
            max_duration (timedelta): Hard cap after the start.
            limit (int): Maximum number of conversations to close in one call.

        Returns:
            List[Conversation]: The conversations that were closed.
        """
        ...


class ConversationEventPublisherPort(Protocol):
    """Publishes conversation events to the event stream they are
    archived from - the caller never knows the broker or the topic.
    """

    async def publish_message_recorded(self, event: ConversationMessageRecorded) -> None:
        """Publish a recorded message.

        Args:
            event (ConversationMessageRecorded): The message event.
        """
        ...


class MessageArchivePort(Protocol):
    """Long-term, append-only store of conversation messages."""

    async def insert_messages(
        self, events: Sequence[ConversationMessageRecorded], *, retention: timedelta
    ) -> None:
        """Store a batch of messages. Re-inserting an already stored
        `message_id` must not produce a second copy.

        Args:
            events (Sequence[ConversationMessageRecorded]): Messages to store.
            retention (timedelta): How long each message is kept after
                its own timestamp before it is deleted.
        """
        ...
