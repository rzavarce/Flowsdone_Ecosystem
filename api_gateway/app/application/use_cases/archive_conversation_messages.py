"""Use case for storing conversation message events in the archive."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Iterable, List

from app.domain.models.conversation_message import (
    MESSAGE_RECORDED_EVENT,
    ConversationMessageRecorded,
)
from app.domain.ports.outbound import MessageArchivePort

logger = logging.getLogger("usecase.archive_conversation_messages")


class ArchiveConversationMessagesUseCase:
    """Turns a batch of raw events from the conversation event stream
    into archived messages, with the platform's retention applied.

    Events of other types are ignored (the stream may carry more types
    later); malformed ones are logged and skipped so a single bad event
    can never block the whole stream.
    """

    def __init__(self, *, archive: MessageArchivePort, retention: timedelta) -> None:
        """Build the use case.

        Args:
            archive (MessageArchivePort): Where messages are stored.
            retention (timedelta): How long messages are kept.
        """
        self._archive = archive
        self._retention = retention

    async def execute(self, raw_events: Iterable[Any]) -> int:
        """Archive the message events in a batch.

        Args:
            raw_events (Iterable[Any]): Decoded events (dicts) as read
                from the event stream.

        Returns:
            int: How many messages were archived.

        Raises:
            Exception: Whatever the archive raises, so the caller does
                not acknowledge the batch and it is retried.
        """
        events: List[ConversationMessageRecorded] = []
        for raw in raw_events:
            if not isinstance(raw, dict) or raw.get("event_type") != MESSAGE_RECORDED_EVENT:
                continue
            try:
                events.append(ConversationMessageRecorded.model_validate(raw))
            except Exception:
                logger.error("conversations.archive.invalid_event", extra={"event": str(raw)[:500]})

        if events:
            await self._archive.insert_messages(events, retention=self._retention)
            logger.info("conversations.archive.inserted", extra={"count": len(events)})
        return len(events)
