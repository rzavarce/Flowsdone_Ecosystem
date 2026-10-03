"""Tests for RabbitMQCrmEvents (persistent events and dead letters)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import aio_pika
import pytest

from app.adapters.outbound.queue.rabbitmq_crm_events import RabbitMQCrmEvents
from app.domain.models.crm import CrmEvent

pytestmark = pytest.mark.anyio


class FakeExchange:
    def __init__(self):
        self.published = []

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))


def _queue():
    queue = RabbitMQCrmEvents(
        url="amqp://x", exchange_name="crm_events", routing_key="crm.event",
        queue_name="crm.events", dead_queue_name="crm.events.dead",
    )
    queue._exchange = FakeExchange()
    return queue


def _event():
    return CrmEvent(
        id=uuid4(), type="handoff.expired", integration_id=uuid4(), handoff_id=uuid4(),
        conversation_id="c1", occurred_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
    )


async def test_events_are_published_persistent_on_the_event_routing_key():
    queue, event = _queue(), _event()

    await queue.publish(event)

    message, routing_key = queue._exchange.published[0]
    assert routing_key == "crm.event"
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert json.loads(message.body)["id"] == str(event.id)


async def test_dead_events_carry_the_reason_on_the_dead_routing_key():
    queue, event = _queue(), _event()

    await queue.publish_dead(event, reason="gave up")

    message, routing_key = queue._exchange.published[0]
    assert routing_key == "crm.event.dead"
    assert json.loads(message.body) == {"event": event.model_dump(mode="json"), "reason": "gave up"}


async def test_publishing_before_start_fails_loudly():
    queue = RabbitMQCrmEvents(url="amqp://x", exchange_name="e", routing_key="k", queue_name="q", dead_queue_name="d")

    with pytest.raises(RuntimeError):
        await queue.publish(_event())
