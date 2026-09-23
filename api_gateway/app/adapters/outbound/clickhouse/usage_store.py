"""ClickHouse implementation of UsageStorePort (table `usage_events`,
schema in scripts/clickhouse/init-clickhouse.sh).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.domain.models.usage import UsageAggregate, UsageEvent
from app.domain.ports.outbound import UsageStorePort

_COLUMNS = (
    "event_id",
    "ts",
    "tenant_id",
    "project_id",
    "conversation_id",
    "message_id",
    "channel_type",
    "trace_id",
    "kind",
    "provider",
    "sku",
    "quantity",
    "unit",
)

# FINAL: collapse re-inserted event ids (ReplacingMergeTree) before summing.
_AGGREGATE_SQL = """
SELECT toString(toDate(ts)) AS day, toString(tenant_id) AS tenant_id, kind, provider, channel_type,
       sku, unit, toString(sum(quantity)) AS quantity
FROM {db}.usage_events FINAL
WHERE ts >= {start:DateTime64(3, 'UTC')} AND ts < {end:DateTime64(3, 'UTC')} %s
GROUP BY day, tenant_id, kind, provider, channel_type, sku, unit
ORDER BY day, tenant_id, kind, provider, sku, unit
"""

_CONVERSATION_SQL = """
SELECT toString(toDate(ts)) AS day, toString(tenant_id) AS tenant_id, kind, provider, channel_type,
       sku, unit, toString(sum(quantity)) AS quantity
FROM {db}.usage_events FINAL
WHERE tenant_id = {tenant:UUID} AND conversation_id = {conversation:UUID}
GROUP BY day, tenant_id, kind, provider, channel_type, sku, unit
ORDER BY day, kind, provider, sku, unit
"""


def _ts(value: datetime) -> str:
    """Format a datetime as a UTC ClickHouse DateTime64(3) literal.

    Args:
        value (datetime): The datetime (naive values are taken as UTC).

    Returns:
        str: "YYYY-MM-DD HH:MM:SS.mmm".
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _to_row(event: UsageEvent) -> Dict[str, Any]:
    """Map a usage event to a `usage_events` row.

    Args:
        event (UsageEvent): The event.

    Returns:
        Dict[str, Any]: The JSONEachRow object.
    """
    return {
        "event_id": str(event.event_id),
        "ts": _ts(event.timestamp),
        "tenant_id": str(event.tenant_id),
        "project_id": str(event.project_id),
        "conversation_id": str(event.conversation_id) if event.conversation_id else None,
        "message_id": str(event.message_id) if event.message_id else None,
        "channel_type": event.channel_type,
        "trace_id": event.trace_id,
        "kind": event.kind,
        "provider": event.provider,
        "sku": event.sku,
        "quantity": str(event.quantity),
        "unit": event.unit,
    }


def _to_aggregate(row: Dict[str, Any]) -> UsageAggregate:
    """Map an aggregate row to a UsageAggregate.

    Args:
        row (Dict[str, Any]): A row of the aggregate queries.

    Returns:
        UsageAggregate: The aggregate.
    """
    return UsageAggregate(
        day=row["day"],
        tenant_id=UUID(row["tenant_id"]),
        kind=row["kind"],
        provider=row["provider"],
        channel_type=row["channel_type"],
        sku=row["sku"],
        unit=row["unit"],
        quantity=Decimal(row["quantity"]),
    )


class ClickHouseUsageStore(UsageStorePort):
    """Stores usage quantities and sums them per day and meter."""

    def __init__(self, client: ClickHouseHttpClient) -> None:
        """Build the store.

        Args:
            client (ClickHouseHttpClient): Client bound to the platform database.
        """
        self._client = client

    async def insert_usage(self, events: Sequence[UsageEvent]) -> None:
        """Store usage events in one insert.

        Args:
            events (Sequence[UsageEvent]): Events to store.
        """
        await self._client.insert_rows("usage_events", _COLUMNS, (_to_row(e) for e in events))

    async def aggregate_daily(
        self, *, start: datetime, end: datetime, tenant_id: Optional[UUID] = None
    ) -> List[UsageAggregate]:
        """Sum usage per day and meter in [start, end).

        Args:
            start (datetime): Inclusive start.
            end (datetime): Exclusive end.
            tenant_id (Optional[UUID]): Only this tenant; all if None.

        Returns:
            List[UsageAggregate]: One row per (day, tenant, meter).
        """
        params: Dict[str, Any] = {"start": _ts(start), "end": _ts(end)}
        tenant_filter = ""
        if tenant_id is not None:
            tenant_filter = "AND tenant_id = {tenant:UUID}"
            params["tenant"] = tenant_id
        rows = await self._client.select(_AGGREGATE_SQL % tenant_filter, params)
        return [_to_aggregate(row) for row in rows]

    async def aggregate_conversation(self, *, tenant_id: UUID, conversation_id: UUID) -> List[UsageAggregate]:
        """Sum one conversation's usage per day and meter.

        Args:
            tenant_id (UUID): Owning tenant.
            conversation_id (UUID): Conversation id.

        Returns:
            List[UsageAggregate]: One row per (day, meter).
        """
        rows = await self._client.select(_CONVERSATION_SQL, {"tenant": tenant_id, "conversation": conversation_id})
        return [_to_aggregate(row) for row in rows]
