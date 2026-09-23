"""Use case for importing LLM token usage from the tracing system."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from app.application.services.usage_metering import usage_from_generation
from app.domain.models.conversation import Conversation
from app.domain.models.usage import UsageEvent
from app.domain.ports.outbound import (
    ConversationRepositoryPort,
    LlmUsageSourcePort,
    SyncCursorRepositoryPort,
    UsageStorePort,
)

logger = logging.getLogger("usecase.sync_llm_usage")

CURSOR_NAME = "llm_usage.langfuse"


@dataclass(frozen=True)
class LlmUsageSyncResult:
    """Outcome of one sync run.

    Attributes:
        start (datetime): Start of the window read.
        end (datetime): End of the window read (the new cursor).
        generations (int): LLM calls read.
        attributed (int): Calls attributed to a conversation.
        unattributed (int): Calls whose session is not a known
            conversation (webchat, playground runs, sessions from before
            conversations existed) - not billed to any tenant.
        events (int): Usage events stored.
    """

    start: datetime
    end: datetime
    generations: int
    attributed: int
    unattributed: int
    events: int


class SyncLlmUsageUseCase:
    """Reads LLM calls since the last run and stores their tokens as
    usage of the conversation (and so the tenant) they belong to.

    The window always re-reads an `overlap` before the cursor, because
    traces reach the tracing system asynchronously and a call may show up
    after its window was first read; re-reading is harmless since event
    ids are deterministic. It also stops `lag` before now for the same
    reason.
    """

    def __init__(
        self,
        *,
        source: LlmUsageSourcePort,
        conversation_repo: ConversationRepositoryPort,
        usage_store: UsageStorePort,
        cursors: SyncCursorRepositoryPort,
        overlap: timedelta = timedelta(hours=1),
        lag: timedelta = timedelta(minutes=2),
        initial_lookback: timedelta = timedelta(days=1),
        max_window: timedelta = timedelta(days=1),
    ) -> None:
        """Build the use case.

        Args:
            source (LlmUsageSourcePort): Where LLM calls are read from.
            conversation_repo (ConversationRepositoryPort): Resolves a
                call's session (conversation id) to its tenant.
            usage_store (UsageStorePort): Where usage is stored.
            cursors (SyncCursorRepositoryPort): Remembers the last window end.
            overlap (timedelta): How much before the cursor to re-read.
            lag (timedelta): How far behind now the window stops.
            initial_lookback (timedelta): Window start on the very first run.
            max_window (timedelta): Largest window read in one run, so a
                long outage is caught up over several runs.
        """
        self._source = source
        self._conversations = conversation_repo
        self._usage = usage_store
        self._cursors = cursors
        self._overlap = overlap
        self._lag = lag
        self._initial_lookback = initial_lookback
        self._max_window = max_window

    async def execute(self, now: datetime) -> LlmUsageSyncResult:
        """Run one sync.

        Args:
            now (datetime): The current time (timezone-aware).

        Returns:
            LlmUsageSyncResult: What was read and stored.
        """
        cursor = await self._cursors.get(CURSOR_NAME)
        start = (cursor - self._overlap) if cursor else (now - self._initial_lookback)
        end = min(now - self._lag, start + self._max_window)
        if end <= start:
            return LlmUsageSyncResult(start, start, 0, 0, 0, 0)

        generations = await self._source.list_generations(start=start, end=end)
        cache: Dict[UUID, Optional[Conversation]] = {}
        events: List[UsageEvent] = []
        attributed = 0
        for generation in generations:
            conversation = await self._conversation_for(generation.session_id, cache)
            if conversation is None:
                continue
            attributed += 1
            events.extend(usage_from_generation(generation, conversation))

        if events:
            await self._usage.insert_usage(events)
        await self._cursors.set(CURSOR_NAME, end)

        result = LlmUsageSyncResult(
            start=start,
            end=end,
            generations=len(generations),
            attributed=attributed,
            unattributed=len(generations) - attributed,
            events=len(events),
        )
        logger.info(
            "usage.llm_sync.done",
            extra={
                "generations": result.generations,
                "attributed": result.attributed,
                "unattributed": result.unattributed,
                "events": result.events,
            },
        )
        return result

    async def _conversation_for(
        self, session_id: Optional[str], cache: Dict[UUID, Optional[Conversation]]
    ) -> Optional[Conversation]:
        """Resolve a trace's session to a conversation, memoized per run.

        Args:
            session_id (Optional[str]): The trace's session id.
            cache (Dict[UUID, Optional[Conversation]]): Per-run memo.

        Returns:
            Optional[Conversation]: The conversation, or None if the session
            is not a conversation id.
        """
        try:
            conversation_id = UUID(session_id or "")
        except ValueError:
            return None
        if conversation_id not in cache:
            cache[conversation_id] = await self._conversations.get(conversation_id)
        return cache[conversation_id]
