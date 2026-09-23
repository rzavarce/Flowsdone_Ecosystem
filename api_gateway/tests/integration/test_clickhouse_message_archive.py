"""Integration test for ClickHouseMessageArchive against a real
ClickHouse with the schema from scripts/clickhouse/init-clickhouse.sh.

Skipped unless TEST_CLICKHOUSE_URL is set (plus TEST_CLICKHOUSE_USER,
TEST_CLICKHOUSE_PASSWORD and TEST_CLICKHOUSE_DATABASE - a throwaway
database, never the real "flowsdone").
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from app.adapters.outbound.conversations.clickhouse_message_archive import ClickHouseMessageArchive
from app.domain.models.conversation_message import ConversationMessageRecorded

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_CLICKHOUSE_URL"), reason="TEST_CLICKHOUSE_URL not set"),
]


async def _query(sql: str) -> str:
    async with httpx.AsyncClient(
        base_url=os.environ["TEST_CLICKHOUSE_URL"],
        headers={
            "X-ClickHouse-User": os.environ["TEST_CLICKHOUSE_USER"],
            "X-ClickHouse-Key": os.environ["TEST_CLICKHOUSE_PASSWORD"],
        },
    ) as client:
        response = await client.post("/", content=sql)
        response.raise_for_status()
        return response.text


async def test_inserted_messages_are_stored_once_even_if_redelivered():
    database = os.environ["TEST_CLICKHOUSE_DATABASE"]
    archive = ClickHouseMessageArchive(
        base_url=os.environ["TEST_CLICKHOUSE_URL"],
        database=database,
        user=os.environ["TEST_CLICKHOUSE_USER"],
        password=os.environ["TEST_CLICKHOUSE_PASSWORD"],
    )
    conversation_id = uuid4()
    event = ConversationMessageRecorded(
        message_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        tenant_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        conversation_id=conversation_id,
        session_id="p:whatsapp_evolution:34600",
        channel_type="whatsapp_evolution",
        channel_connection_id=uuid4(),
        direction="inbound",
        sender_type="contact",
        app="langflow",
        contact="34600",
        text="hola 'mundo' ñ",
    )
    try:
        await archive.insert_messages([event], retention=timedelta(days=183))
        await archive.insert_messages([event], retention=timedelta(days=183))
    finally:
        await archive.aclose()

    result = await _query(
        f"SELECT count(), any(text), any(direction) FROM {database}.messages FINAL "
        f"WHERE conversation_id = '{conversation_id}' FORMAT TSV"
    )
    assert result.strip().split("\t") == ["1", "hola \\'mundo\\' ñ", "inbound"]
