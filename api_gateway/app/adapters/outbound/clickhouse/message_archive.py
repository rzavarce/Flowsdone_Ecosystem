"""ClickHouse implementation of MessageArchivePort (table `messages`,
schema in scripts/clickhouse/init-clickhouse.sh).
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Any, Dict, List, Sequence
from uuid import UUID

from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.ports.outbound import MessageArchivePort

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

# FINAL collapses redelivered message ids (ReplacingMergeTree); the
# tenant_id filter uses the table's primary key and enforces isolation.
_LIST_SQL = """
SELECT toString(message_id) AS message_id, toString(ts) AS ts, toString(tenant_id) AS tenant_id,
       toString(project_id) AS project_id, toString(agent_id) AS agent_id,
       toString(conversation_id) AS conversation_id, session_id, channel_type,
       toString(channel_connection_id) AS channel_connection_id, toString(direction) AS direction,
       sender_type, app, contact, text
FROM {db}.messages FINAL
WHERE tenant_id = {tenant:UUID} AND conversation_id = {conversation:UUID}
ORDER BY ts, message_id
LIMIT {limit:UInt32}
"""


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


class ClickHouseMessageArchive(MessageArchivePort):
    """Stores and reads conversation messages.

    The table is a ReplacingMergeTree keyed on the message id, so a
    redelivered event collapses into the row it duplicates; each row
    carries its own `retention_until`, which the table's TTL deletes it at.
    """

    def __init__(self, client: ClickHouseHttpClient) -> None:
        """Build the archive.

        Args:
            client (ClickHouseHttpClient): Client bound to the platform database.
        """
        self._client = client

    async def insert_messages(
        self, events: Sequence[ConversationMessageRecorded], *, retention: timedelta
    ) -> None:
        """Insert a batch of messages in a single request.

        Args:
            events (Sequence[ConversationMessageRecorded]): Messages to store.
            retention (timedelta): How long each message is kept after
                its own timestamp.
        """
        await self._client.insert_rows("messages", _COLUMNS, (_to_row(e, retention) for e in events))

    async def list_messages(
        self, *, tenant_id: UUID, conversation_id: UUID, limit: int = 500
    ) -> List[ConversationMessageRecorded]:
        """A conversation's messages, oldest first.

        Args:
            tenant_id (UUID): Owning tenant.
            conversation_id (UUID): Conversation id.
            limit (int): Maximum number of messages.

        Returns:
            List[ConversationMessageRecorded]: The messages.
        """
        rows = await self._client.select(
            _LIST_SQL, {"tenant": tenant_id, "conversation": conversation_id, "limit": limit}
        )
        return [
            ConversationMessageRecorded.model_validate({**row, "timestamp": row.pop("ts") + "+00:00"})
            for row in rows
        ]
