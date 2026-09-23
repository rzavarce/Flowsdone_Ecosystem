"""Use case for the periodic sweep that closes idle conversations."""

from __future__ import annotations

import logging
from datetime import datetime

from app.application.services.conversation_tracker import record_closed_event
from app.domain.models.conversation import ConversationLifecyclePolicy
from app.domain.ports.outbound import ConversationRepositoryPort, SessionHistoryRepositoryPort

logger = logging.getLogger("usecase.close_expired_conversations")


class CloseExpiredConversationsUseCase:
    """Closes open conversations the contact never came back to.

    ConversationTracker already closes an expired conversation when the
    contact writes again; this sweep covers the ones where they never
    do, so "open" in the inbox and conversation durations stay accurate.
    Safe to run concurrently or repeatedly: only still-open
    conversations are closed.
    """

    def __init__(
        self,
        *,
        conversation_repo: ConversationRepositoryPort,
        session_history_repo: SessionHistoryRepositoryPort,
        policy: ConversationLifecyclePolicy,
        batch_size: int = 500,
    ) -> None:
        """Build the use case.

        Args:
            conversation_repo (ConversationRepositoryPort): Live
                conversation records.
            session_history_repo (SessionHistoryRepositoryPort): Audit
                log that gets a "closed" event per closed conversation.
            policy (ConversationLifecyclePolicy): When a conversation ends.
            batch_size (int): Maximum conversations closed per batch.
        """
        self._conversations = conversation_repo
        self._history = session_history_repo
        self._policy = policy
        self._batch_size = batch_size

    async def execute(self, now: datetime) -> int:
        """Close every conversation that has expired by `now`.

        Args:
            now (datetime): The current time (timezone-aware).

        Returns:
            int: How many conversations were closed.
        """
        total = 0
        while True:
            closed = await self._conversations.close_expired(
                now=now,
                inactivity=self._policy.inactivity,
                max_duration=self._policy.max_duration,
                limit=self._batch_size,
            )
            for conversation in closed:
                await record_closed_event(self._history, conversation, reason=conversation.close_reason or "")
            total += len(closed)
            if len(closed) < self._batch_size:
                break

        if total:
            logger.info("conversations.sweep.closed", extra={"count": total})
        return total
