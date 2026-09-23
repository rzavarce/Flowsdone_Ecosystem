"""Tests for KafkaBatchConsumer, with aiokafka's consumer faked."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.adapters.inbound.queue import kafka_batch_consumer as module
from app.adapters.inbound.queue.kafka_batch_consumer import KafkaBatchConsumer

pytestmark = pytest.mark.anyio


class _StopLoop(Exception):
    pass


class _FakeAIOKafkaConsumer:
    """Serves pre-baked batches, then stops the endless loop."""

    def __init__(self, *_args, value_deserializer, **_kwargs) -> None:
        self._deserialize = value_deserializer
        self.batches = []
        self.commits = 0
        self.seeks = []
        self.committed_offsets = {}
        self.stopped = False

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self.stopped = True

    async def getmany(self, *, timeout_ms, max_records):
        if not self.batches:
            raise _StopLoop()
        batch = self.batches.pop(0)
        return {
            partition: [SimpleNamespace(value=self._deserialize(raw)) for raw in raws]
            for partition, raws in batch.items()
        }

    async def commit(self) -> None:
        self.commits += 1

    async def committed(self, partition):
        return self.committed_offsets.get(partition)

    def seek(self, partition, offset) -> None:
        self.seeks.append((partition, offset))

    async def seek_to_beginning(self, partition) -> None:
        self.seeks.append((partition, "beginning"))


def _consumer(monkeypatch) -> tuple[KafkaBatchConsumer, _FakeAIOKafkaConsumer]:
    holder = {}

    def constructor(*args, **kwargs):
        holder["fake"] = _FakeAIOKafkaConsumer(*args, **kwargs)
        return holder["fake"]

    monkeypatch.setattr(module, "AIOKafkaConsumer", constructor)
    consumer = KafkaBatchConsumer(
        bootstrap_servers="kafka:9092", topic="conversation.events", group_id="g", retry_backoff_seconds=0
    )
    return consumer, holder["fake"]


def _raw(value) -> bytes:
    return json.dumps(value).encode()


async def test_hands_each_batch_to_the_handler_and_commits_after_it(monkeypatch):
    consumer, fake = _consumer(monkeypatch)
    fake.batches = [{"p0": [_raw({"a": 1}), b"not json"], "p1": [_raw({"b": 2})]}, {}]
    received = []

    async def handler(values):
        received.append(values)

    with pytest.raises(_StopLoop):
        await consumer.start(handler)

    assert received == [[{"a": 1}, None, {"b": 2}]]
    assert fake.commits == 1
    assert fake.stopped


async def test_failed_batch_is_not_committed_and_partitions_are_rewound(monkeypatch):
    consumer, fake = _consumer(monkeypatch)
    fake.batches = [{"p0": [_raw({"a": 1})], "p1": [_raw({"b": 2})]}]
    fake.committed_offsets = {"p0": 41}

    async def handler(values):
        raise RuntimeError("clickhouse down")

    with pytest.raises(_StopLoop):
        await consumer.start(handler)

    assert fake.commits == 0
    assert fake.seeks == [("p0", 41), ("p1", "beginning")]
