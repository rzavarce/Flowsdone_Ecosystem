"""Use case for storing conversation message events in the archive."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Iterable, List, Optional

from app.application.services.usage_metering import usage_from_message
from app.domain.models.conversation_message import (
    MESSAGE_RECORDED_EVENT,
    ConversationMessageRecorded,
)
from app.domain.ports.outbound import MessageArchivePort, UsageStorePort

logger = logging.getLogger("usecase.archive_conversation_messages")


class ArchiveConversationMessagesUseCase:
    """Turns a batch of raw events from the conversation event stream
    into archived messages, with the platform's retention applied, and
    meters the channel/platform usage those messages represent.

    Events of other types are ignored (the stream may carry more types
    later); malformed ones are logged and skipped so a single bad event
    can never block the whole stream.
    """

    def __init__(
        self,
        *,
        archive: MessageArchivePort,
        retention: timedelta,
        usage_store: Optional[UsageStorePort] = None,
    ) -> None:
        """Build the use case.

        Args:
            archive (MessageArchivePort): Where messages are stored.
            retention (timedelta): How long messages are kept.
            usage_store (Optional[UsageStorePort]): Where the usage
                derived from each message is stored; skipped if None.
        """
        self._archive = archive
        self._retention = retention
        self._usage = usage_store

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
            if self._usage is not None:
                # Idempotent too (deterministic event ids): if this fails
                # after the messages went in, the retried batch re-inserts
                # both without duplicating either.
                await self._usage.insert_usage([u for e in events for u in usage_from_message(e)])
            logger.info("conversations.archive.inserted", extra={"count": len(events)})
        return len(events)
