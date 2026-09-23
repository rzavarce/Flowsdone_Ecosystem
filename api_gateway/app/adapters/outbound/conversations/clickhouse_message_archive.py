"""ClickHouse implementation of MessageArchivePort, over ClickHouse's
HTTP interface (plain httpx - no extra client library).
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta, timezone
from typing import Any, Dict, Optional, Sequence

import httpx

from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.ports.outbound import MessageArchivePort

logger = logging.getLogger("conversations.clickhouse_archive")

_COLUMNS = (
    "message_id",
    "ts",
    "tenant_id",
    "project_id",
    "agent_id",
    "conversation_id",
    "session_id",
    "channel_type",
    "channel_connection_id",
    "direction",
    "sender_type",
    "app",
    "contact",
    "text",
    "retention_until",
)


class ClickHouseArchiveError(Exception):
    """Raised when ClickHouse rejects an insert."""


class ClickHouseMessageArchive(MessageArchivePort):
    """Inserts messages into `<database>.messages` (schema in
    scripts/clickhouse/init-clickhouse.sh).

    The table is a ReplacingMergeTree keyed on the message id, so a
    redelivered event collapses into the row it duplicates; each row
    carries its own `retention_until`, which the table's TTL deletes it
    at.
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        user: str,
        password: Optional[str],
        timeout_seconds: float = 10.0,
    ) -> None:
        """Build the archive.

        Args:
            base_url (str): ClickHouse HTTP endpoint (e.g. http://clickhouse:8123).
            database (str): Database holding the `messages` table.
            user (str): ClickHouse user.
            password (Optional[str]): Password of that user.
            timeout_seconds (float): HTTP timeout per insert.
        """
        headers = {"X-ClickHouse-User": user}
        if password:
            headers["X-ClickHouse-Key"] = password
        self._database = database
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=httpx.Timeout(timeout_seconds)
        )

    async def insert_messages(
        self, events: Sequence[ConversationMessageRecorded], *, retention: timedelta
    ) -> None:
        """Insert a batch of messages in a single request.

        Args:
            events (Sequence[ConversationMessageRecorded]): Messages to store.
            retention (timedelta): How long each message is kept after
                its own timestamp.

        Raises:
            ClickHouseArchiveError: If ClickHouse answers with an error.
        """
        if not events:
            return

        body = "\n".join(json.dumps(_to_row(event, retention)) for event in events)
        query = f"INSERT INTO {self._database}.messages ({', '.join(_COLUMNS)}) FORMAT JSONEachRow"
        response = await self._client.post(
            "/",
            params={"query": query, "date_time_input_format": "best_effort"},
            content=body.encode("utf-8"),
        )
        if response.status_code >= 400:
            logger.error(
                "conversations.clickhouse.insert_failed",
                extra={"status_code": response.status_code, "response_text": response.text[:500]},
            )
            raise ClickHouseArchiveError(f"ClickHouse insert failed ({response.status_code}): {response.text[:500]}")

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


def _to_row(event: ConversationMessageRecorded, retention: timedelta) -> Dict[str, Any]:
    """Map an event to a `messages` row, timestamps in UTC.

    Args:
        event (ConversationMessageRecorded): The message event.
        retention (timedelta): How long the row is kept.

    Returns:
        Dict[str, Any]: The JSONEachRow object for the row.
    """
    ts = event.timestamp.astimezone(timezone.utc)
    return {
        "message_id": str(event.message_id),
        "ts": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "tenant_id": str(event.tenant_id),
        "project_id": str(event.project_id),
        "agent_id": str(event.agent_id),
        "conversation_id": str(event.conversation_id),
        "session_id": event.session_id,
        "channel_type": event.channel_type,
        "channel_connection_id": str(event.channel_connection_id),
        "direction": event.direction,
        "sender_type": event.sender_type,
        "app": event.app,
        "contact": event.contact,
        "text": event.text,
        "retention_until": (ts + retention).strftime("%Y-%m-%d %H:%M:%S"),
    }
