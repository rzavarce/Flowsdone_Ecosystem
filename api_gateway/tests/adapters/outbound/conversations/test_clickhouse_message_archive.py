"""Tests for ClickHouseMessageArchive (HTTP interface, faked)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.adapters.outbound.conversations import clickhouse_message_archive as module
from app.adapters.outbound.conversations.clickhouse_message_archive import (
    ClickHouseArchiveError,
    ClickHouseMessageArchive,
)
from app.domain.models.conversation_message import ConversationMessageRecorded
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


def _event(**overrides) -> ConversationMessageRecorded:
    defaults = dict(
        message_id=uuid4(),
        timestamp=datetime(2026, 9, 1, 12, 30, 15, 123456, tzinfo=timezone.utc),
        tenant_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        conversation_id=uuid4(),
        session_id="p:whatsapp_evolution:34600",
        channel_type="whatsapp_evolution",
        channel_connection_id=uuid4(),
        direction="inbound",
        sender_type="contact",
        app="langflow",
        contact="34600",
        text='hola "mundo"',
    )
    defaults.update(overrides)
    return ConversationMessageRecorded(**defaults)


def _archive(monkeypatch, response: FakeResponse) -> tuple[ClickHouseMessageArchive, FakeAsyncClient]:
    fake = FakeAsyncClient(lambda call: response)
    captured = {}

    def constructor(*args, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(module.httpx, "AsyncClient", constructor)
    archive = ClickHouseMessageArchive(
        base_url="http://clickhouse:8123", database="flowsdone", user="flowsdone_app", password="secret"
    )
    fake.constructor_kwargs = captured
    return archive, fake


async def test_inserts_the_batch_as_json_each_row_in_one_request(monkeypatch):
    archive, fake = _archive(monkeypatch, FakeResponse(200))
    first, second = _event(), _event(direction="outbound", sender_type="bot", text="respuesta")

    await archive.insert_messages([first, second], retention=timedelta(days=183))

    [call] = fake.calls
    assert call.method == "POST"
    assert call.kwargs["params"]["query"].startswith("INSERT INTO flowsdone.messages (message_id, ts,")
    assert call.kwargs["params"]["query"].endswith("FORMAT JSONEachRow")
    rows = [json.loads(line) for line in call.kwargs["content"].decode().splitlines()]
    assert rows[0]["message_id"] == str(first.message_id)
    assert rows[0]["ts"] == "2026-09-01 12:30:15.123"
    assert rows[0]["retention_until"] == "2027-03-03 12:30:15"
    assert rows[0]["text"] == 'hola "mundo"'
    assert rows[1]["direction"] == "outbound"
    assert rows[1]["sender_type"] == "bot"
    assert fake.constructor_kwargs["headers"] == {"X-ClickHouse-User": "flowsdone_app", "X-ClickHouse-Key": "secret"}


async def test_empty_batch_makes_no_request(monkeypatch):
    archive, fake = _archive(monkeypatch, FakeResponse(200))

    await archive.insert_messages([], retention=timedelta(days=183))

    assert fake.calls == []


async def test_raises_when_clickhouse_rejects_the_insert(monkeypatch):
    archive, _ = _archive(monkeypatch, FakeResponse(500, text="Code: 60. Table does not exist"))

    with pytest.raises(ClickHouseArchiveError):
        await archive.insert_messages([_event()], retention=timedelta(days=183))
