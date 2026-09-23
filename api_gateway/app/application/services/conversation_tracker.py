"""ConversationTracker: keeps each Switchboard Session attached to its
current Conversation and records every message into the conversation
event stream.

Called by Switchboard for inbound turns and by
HandleOutboundResponseUseCase for delivered replies. It is the only
place that decides when a conversation ends and a new one starts (see
ConversationLifecyclePolicy).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.domain.models.conversation import Conversation, ConversationLifecyclePolicy
from app.domain.models.conversation_message import ConversationMessageRecorded, MessageSenderType
from app.domain.models.session import MessageDirection, Session
from app.domain.ports.outbound import (
    ConversationEventPublisherPort,
    ConversationRepositoryPort,
    SessionHistoryRepositoryPort,
)

logger = logging.getLogger("conversations.tracker")


class ConversationTracker:
    """Resolves/rotates a session's conversation and records messages.

    Sets `session.conversation_id` in place; the caller is responsible
    for persisting the session afterwards (Switchboard and the outbound
    handler already save it after every turn).
    """

    def __init__(
        self,
        *,
        conversation_repo: ConversationRepositoryPort,
        event_publisher: ConversationEventPublisherPort,
        session_history_repo: SessionHistoryRepositoryPort,
        policy: ConversationLifecyclePolicy,
    ) -> None:
        """Build the tracker.

        Args:
            conversation_repo (ConversationRepositoryPort): Live
                conversation records.
            event_publisher (ConversationEventPublisherPort): Where
                recorded messages are published for archiving.
            session_history_repo (SessionHistoryRepositoryPort): Audit
                log that gets a "closed" event when a conversation ends.
            policy (ConversationLifecyclePolicy): When a conversation ends.
        """
        self._conversations = conversation_repo
        self._events = event_publisher
        self._history = session_history_repo
        self._policy = policy

    async def record_inbound(self, *, session: Session, text: str, now: datetime) -> Conversation:
        """Record a message from the contact, opening a new conversation
        first if the session has none or its current one has expired.

        Args:
            session (Session): The contact's session; its
                `conversation_id` is updated in place.
            text (str): The message text.
            now (datetime): When the message arrived (timezone-aware).

        Returns:
            Conversation: The conversation the message was recorded in.
        """
        conversation = await self._current_or_new(session, now)
        session.conversation_id = conversation.id

        await self._conversations.record_message(conversation.id, direction="inbound", at=now)
        await self._publish(session, conversation, direction="inbound", sender_type="contact", text=text, now=now)
        return conversation

    async def record_outbound(
        self,
        *,
        session: Session,
        text: str,
        now: datetime,
        sender_type: MessageSenderType = "bot",
    ) -> Optional[Conversation]:
        """Record a message sent to the contact in the session's current
        conversation. Never opens a conversation: only the contact does.

        Args:
            session (Session): The contact's session.
            text (str): The message text.
            now (datetime): When the message was sent (timezone-aware).
            sender_type (MessageSenderType): Who wrote it ("bot" for an
                app such as Langflow, "human" for a human agent).

        Returns:
            Optional[Conversation]: The conversation it was recorded in,
            or None if the session has no known conversation (a session
            stored before conversations existed).
        """
        if session.conversation_id is None:
            return None

        conversation = await self._conversations.get(session.conversation_id)
        if conversation is None:
            logger.warning(
                "conversations.outbound.unknown_conversation",
                extra={"session_id": session.id, "conversation_id": str(session.conversation_id)},
            )
            return None

        # A late reply to an already-expired conversation still belongs
        # to it - it answers a message that was sent inside it.
        await self._conversations.record_message(conversation.id, direction="outbound", at=now)
        await self._publish(session, conversation, direction="outbound", sender_type=sender_type, text=text, now=now)
        return conversation

    async def _current_or_new(self, session: Session, now: datetime) -> Conversation:
        """Return the session's conversation if still current, otherwise
        close it (when expired but still open) and open a new one.

        Args:
            session (Session): The contact's session.
            now (datetime): The current time.

        Returns:
            Conversation: The conversation to record the message in.
        """
        if session.conversation_id is not None:
            current = await self._conversations.get(session.conversation_id)
            if current is not None:
                if not self._policy.is_expired(current, now):
                    return current
                if current.status == "open":
                    expiry = self._policy.expiry(current)
                    await self._close(current, reason=expiry.reason, closed_at=expiry.at)

        conversation = await self._conversations.open(
            Conversation(
                id=uuid4(),
                session_id=session.id,
                tenant_id=session.tenant_id,
                project_id=session.project_id,
                agent_id=session.agent_id,
                channel_type=session.channel_type,
                channel_connection_id=session.channel_connection_id,
                contact=session.user_identifier,
                started_at=now,
                last_inbound_at=now,
                last_message_at=now,
            )
        )
        logger.info(
            "conversations.opened",
            extra={"session_id": session.id, "conversation_id": str(conversation.id)},
        )
        return conversation

    async def _close(self, conversation: Conversation, *, reason: str, closed_at: datetime) -> None:
        """Close a conversation and log the lifecycle event.

        Args:
            conversation (Conversation): The conversation to close.
            reason (str): Why it ends ("inactivity", "max_duration", ...).
            closed_at (datetime): When it ended.
        """
        closed = await self._conversations.close(conversation.id, reason=reason, closed_at=closed_at)
        if closed:
            await record_closed_event(self._history, conversation, reason=reason)

    async def _publish(
        self,
        session: Session,
        conversation: Conversation,
        *,
        direction: MessageDirection,
        sender_type: MessageSenderType,
        text: str,
        now: datetime,
    ) -> None:
        """Publish a recorded message to the conversation event stream.

        Args:
            session (Session): The contact's session.
            conversation (Conversation): The conversation it belongs to.
            direction (MessageDirection): "inbound" or "outbound".
            sender_type (MessageSenderType): Who wrote it.
            text (str): The message text.
            now (datetime): When it happened.
        """
        await self._events.publish_message_recorded(
            ConversationMessageRecorded(
                message_id=uuid4(),
                timestamp=now,
                tenant_id=conversation.tenant_id,
                project_id=conversation.project_id,
                agent_id=conversation.agent_id,
                conversation_id=conversation.id,
                session_id=session.id,
                channel_type=conversation.channel_type,
                channel_connection_id=conversation.channel_connection_id,
                direction=direction,
                sender_type=sender_type,
                app=session.current_app,
                contact=conversation.contact,
                text=text,
            )
        )


async def record_closed_event(
    history: SessionHistoryRepositoryPort, conversation: Conversation, *, reason: str
) -> None:
    """Append a "closed" lifecycle event for a conversation to the
    session audit log.

    Shared by ConversationTracker (conversation closed lazily when the
    contact writes again) and CloseExpiredConversationsUseCase (closed
    by the periodic sweep).

    Args:
        history (SessionHistoryRepositoryPort): The session audit log.
        conversation (Conversation): The conversation that was closed.
        reason (str): Why it was closed.
    """
    await history.append_event(
        session_id=conversation.session_id,
        project_id=conversation.project_id,
        event_type="closed",
        reason=f"conversation {conversation.id}: {reason}",
    )
