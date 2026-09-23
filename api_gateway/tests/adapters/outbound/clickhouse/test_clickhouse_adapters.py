"""Tests for the ClickHouse adapters (HTTP interface faked)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.adapters.outbound.clickhouse import http_client as module
from app.adapters.outbound.clickhouse.http_client import ClickHouseError, ClickHouseHttpClient
from app.adapters.outbound.clickhouse.message_archive import ClickHouseMessageArchive
from app.adapters.outbound.clickhouse.usage_store import ClickHouseUsageStore
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.models.usage import UsageEvent
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


def _client(monkeypatch, responder):
    fake = FakeAsyncClient(responder)
    captured = {}

    def constructor(*args, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(module.httpx, "AsyncClient", constructor)
    client = ClickHouseHttpClient(base_url="http://ch:8123", database="flowsdone", user="app", password="pw")
    return client, fake, captured


def _message(**overrides) -> ConversationMessageRecorded:
    defaults = dict(
        message_id=uuid4(), timestamp=datetime(2026, 9, 1, 12, 30, 15, 123456, tzinfo=timezone.utc),
        tenant_id=uuid4(), project_id=uuid4(), agent_id=uuid4(), conversation_id=uuid4(),
        session_id="p:whatsapp_evolution:34600", channel_type="whatsapp_evolution",
        channel_connection_id=uuid4(), direction="inbound", sender_type="contact", app="langflow",
        contact="34600", text='hola "mundo"',
    )
    defaults.update(overrides)
    return ConversationMessageRecorded(**defaults)


async def test_client_authenticates_with_headers(monkeypatch):
    _, _, captured = _client(monkeypatch, lambda call: FakeResponse(200))

    assert captured["headers"] == {"X-ClickHouse-User": "app", "X-ClickHouse-Key": "pw"}


async def test_select_sends_values_as_query_parameters_never_in_the_sql(monkeypatch):
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200, text='{"a":1}\n{"a":2}\n'))

    rows = await client.select("SELECT a FROM {db}.t WHERE x = {x:String}", {"x": "'; DROP TABLE t"})

    [call] = fake.calls
    assert rows == [{"a": 1}, {"a": 2}]
    assert call.kwargs["params"] == {"param_x": "'; DROP TABLE t", "prefer_column_name_to_alias": "1"}
    sql = call.kwargs["content"].decode()
    assert "flowsdone.t" in sql and "DROP" not in sql and sql.endswith("FORMAT JSONEachRow")


async def test_errors_raise(monkeypatch):
    client, _, _ = _client(monkeypatch, lambda call: FakeResponse(500, text="Code: 60"))

    with pytest.raises(ClickHouseError):
        await client.select("SELECT 1")


async def test_empty_insert_makes_no_request(monkeypatch):
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200))

    await client.insert_rows("messages", ["a"], [])

    assert fake.calls == []


async def test_archive_inserts_messages_as_json_each_row(monkeypatch):
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200))
    first, second = _message(), _message(direction="outbound", sender_type="bot")

    await ClickHouseMessageArchive(client).insert_messages([first, second], retention=timedelta(days=183))

    [call] = fake.calls
    assert call.kwargs["params"]["query"].startswith("INSERT INTO flowsdone.messages (message_id, ts,")
    rows = [json.loads(line) for line in call.kwargs["content"].decode().splitlines()]
    assert rows[0]["message_id"] == str(first.message_id)
    assert rows[0]["ts"] == "2026-09-01 12:30:15.123"
    assert rows[0]["retention_until"] == "2027-03-03 12:30:15"
    assert rows[0]["text"] == 'hola "mundo"'
    assert rows[1]["direction"] == "outbound"


async def test_archive_lists_messages_scoped_to_tenant(monkeypatch):
    message = _message()
    row = {
        "message_id": str(message.message_id), "ts": "2026-09-01 12:30:15.123",
        "tenant_id": str(message.tenant_id), "project_id": str(message.project_id),
        "agent_id": str(message.agent_id), "conversation_id": str(message.conversation_id),
        "session_id": message.session_id, "channel_type": message.channel_type,
        "channel_connection_id": str(message.channel_connection_id), "direction": "inbound",
        "sender_type": "contact", "app": "langflow", "contact": "34600", "text": "hola",
    }
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200, text=json.dumps(row)))

    [listed] = await ClickHouseMessageArchive(client).list_messages(
        tenant_id=message.tenant_id, conversation_id=message.conversation_id, limit=50
    )

    assert listed.message_id == message.message_id
    assert listed.timestamp == datetime(2026, 9, 1, 12, 30, 15, 123000, tzinfo=timezone.utc)
    assert fake.calls[0].kwargs["params"] == {
        "param_tenant": str(message.tenant_id), "param_conversation": str(message.conversation_id), "param_limit": "50",
        "prefer_column_name_to_alias": "1",
    }


async def test_usage_store_inserts_and_aggregates(monkeypatch):
    tenant = uuid4()
    aggregate_row = {
        "day": "2026-09-01", "tenant_id": str(tenant), "kind": "llm", "provider": "openai",
        "channel_type": "telegram", "sku": "gpt-4.1-mini", "unit": "input_token", "quantity": "1500",
    }
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200, text=json.dumps(aggregate_row)))
    store = ClickHouseUsageStore(client)
    event = UsageEvent(
        event_id=uuid4(), timestamp=datetime(2026, 9, 1, 12, tzinfo=timezone.utc), tenant_id=tenant,
        project_id=uuid4(), conversation_id=None, kind="llm", provider="openai", sku="gpt-4.1-mini",
        quantity=Decimal("1500"), unit="input_token",
    )

    await store.insert_usage([event])
    [aggregate] = await store.aggregate_daily(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc), end=datetime(2026, 10, 1, tzinfo=timezone.utc), tenant_id=tenant
    )

    inserted = json.loads(fake.calls[0].kwargs["content"].decode())
    assert inserted["quantity"] == "1500" and inserted["conversation_id"] is None
    select = fake.calls[1]
    assert "tenant_id = {tenant:UUID}" in select.kwargs["content"].decode()
    assert select.kwargs["params"]["param_start"] == "2026-09-01 00:00:00.000"
    assert aggregate.quantity == Decimal(1500) and aggregate.tenant_id == tenant and str(aggregate.day) == "2026-09-01"


async def test_usage_store_all_tenants_has_no_tenant_filter(monkeypatch):
    client, fake, _ = _client(monkeypatch, lambda call: FakeResponse(200, text=""))

    assert await ClickHouseUsageStore(client).aggregate_daily(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc), end=datetime(2026, 10, 1, tzinfo=timezone.utc)
    ) == []
    assert "{tenant:UUID}" not in fake.calls[0].kwargs["content"].decode()
