"""Ports for usage metering: where usage is stored and aggregated, the
cost catalog, where LLM usage comes from, and sync cursors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Protocol, Sequence
from uuid import UUID

from app.domain.models.usage import CostRate, UsageAggregate, UsageEvent


class UsageStorePort(Protocol):
    """Append-only store of usage quantities (ClickHouse in production)."""

    async def insert_usage(self, events: Sequence[UsageEvent]) -> None:
        """Store usage events; re-inserting an `event_id` must not count twice.

        Args:
            events (Sequence[UsageEvent]): Events to store.
        """
        ...

    async def aggregate_daily(
        self, *, start: datetime, end: datetime, tenant_id: Optional[UUID] = None
    ) -> List[UsageAggregate]:
        """Sum usage per day and meter in [start, end).

        Args:
            start (datetime): Inclusive start.
            end (datetime): Exclusive end.
            tenant_id (Optional[UUID]): Only this tenant; all tenants if None.

        Returns:
            List[UsageAggregate]: One row per (day, tenant, meter).
        """
        ...

    async def aggregate_conversation(self, *, tenant_id: UUID, conversation_id: UUID) -> List[UsageAggregate]:
        """Sum one conversation's usage per day and meter.

        Args:
            tenant_id (UUID): Owning tenant (part of the storage key).
            conversation_id (UUID): Conversation id.

        Returns:
            List[UsageAggregate]: One row per (day, meter).
        """
        ...


class CostRateRepositoryPort(Protocol):
    """The versioned cost catalog (append-only: rates are never edited)."""

    async def list_all(self) -> List[CostRate]:
        """Every rate, newest first.

        Returns:
            List[CostRate]: All rates.
        """
        ...

    async def create(self, rate: CostRate) -> CostRate:
        """Store a new rate (or a new version of an existing meter's price).

        Args:
            rate (CostRate): The rate.

        Returns:
            CostRate: The stored rate.
        """
        ...

    async def delete(self, rate_id: UUID) -> bool:
        """Delete a rate entered by mistake.

        Args:
            rate_id (UUID): Rate id.

        Returns:
            bool: True if it existed.
        """
        ...


@dataclass(frozen=True)
class LlmGeneration:
    """One LLM call as reported by the tracing system.

    Attributes:
        id (str): Id of the observation in the tracing system.
        trace_id (str): Id of its trace.
        session_id (Optional[str]): Session of the trace - the Conversation
            id for channels going through Switchboard.
        model (str): Model name as reported.
        start_time (datetime): When the call started.
        input_tokens (int): Non-cached input tokens.
        output_tokens (int): Output tokens.
        cached_input_tokens (int): Input tokens served from cache.
    """

    id: str
    trace_id: str
    session_id: Optional[str]
    model: str
    start_time: datetime
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


class LlmUsageSourcePort(Protocol):
    """Where LLM token usage is read from (Langfuse in production)."""

    async def list_generations(self, *, start: datetime, end: datetime) -> List[LlmGeneration]:
        """LLM calls that started in [start, end).

        Args:
            start (datetime): Inclusive start.
            end (datetime): Exclusive end.

        Returns:
            List[LlmGeneration]: The calls, with their session resolved.
        """
        ...


class SyncCursorRepositoryPort(Protocol):
    """Remembers up to when a periodic sync has processed its source."""

    async def get(self, name: str) -> Optional[datetime]:
        """Read a cursor.

        Args:
            name (str): Cursor name.

        Returns:
            Optional[datetime]: Its position, or None if never set.
        """
        ...

    async def set(self, name: str, position: datetime) -> None:
        """Move a cursor.

        Args:
            name (str): Cursor name.
            position (datetime): New position.
        """
        ...
