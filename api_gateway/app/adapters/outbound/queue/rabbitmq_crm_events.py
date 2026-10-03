"""RabbitMQ queue for CRM events: persistent messages, a durable queue
declared up front (so nothing is dropped while the worker is down) and a
dead-letter queue for events that could not be delivered.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import aio_pika

from app.domain.models.crm import CrmEvent
from app.domain.ports.outbound import CrmDeadLetterPort, CrmEventPublisherPort

logger = logging.getLogger("rabbitmq.crm_events")


class RabbitMQCrmEvents(CrmEventPublisherPort, CrmDeadLetterPort):
    """Publishes CRM events (and parks dead ones) on RabbitMQ."""

    def __init__(self, *, url: str, exchange_name: str, routing_key: str, queue_name: str, dead_queue_name: str) -> None:
        """Build the publisher.

        Args:
            url (str): RabbitMQ connection URL.
            exchange_name (str): Topic exchange of the CRM events.
            routing_key (str): Routing key of the events.
            queue_name (str): Durable queue the crm_worker consumes.
            dead_queue_name (str): Durable queue for undeliverable events.
        """
        self._url = url
        self._exchange_name = exchange_name
        self._routing_key = routing_key
        self._dead_routing_key = f"{routing_key}.dead"
        self._queue_name = queue_name
        self._dead_queue_name = dead_queue_name
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._exchange: Optional[aio_pika.abc.AbstractExchange] = None

    async def start(self) -> None:
        """Connect, and declare the exchange and both queues with their bindings."""
        self._connection = await aio_pika.connect_robust(self._url)
        channel = await self._connection.channel()
        self._exchange = await channel.declare_exchange(self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(self._queue_name, durable=True)
        await queue.bind(self._exchange, routing_key=self._routing_key)
        dead = await channel.declare_queue(self._dead_queue_name, durable=True)
        await dead.bind(self._exchange, routing_key=self._dead_routing_key)
        logger.info("rabbitmq.crm_events.ready", extra={"exchange": self._exchange_name, "queue": self._queue_name})

    async def stop(self) -> None:
        """Close the connection, if open."""
        if self._connection:
            await self._connection.close()

    async def publish(self, event: CrmEvent) -> None:
        """Queue an event for delivery.

        Args:
            event (CrmEvent): The event.
        """
        await self._send(event.model_dump(mode="json"), self._routing_key)

    async def publish_dead(self, event: CrmEvent, *, reason: str) -> None:
        """Park an undeliverable event in the dead-letter queue.

        Args:
            event (CrmEvent): The event.
            reason (str): Why it was given up on.
        """
        await self._send({"event": event.model_dump(mode="json"), "reason": reason}, self._dead_routing_key)

    async def _send(self, body: dict, routing_key: str) -> None:
        """Publish a persistent JSON message.

        Args:
            body (dict): JSON-serializable body.
            routing_key (str): Where it goes.

        Raises:
            RuntimeError: If the publisher has not been started.
        """
        if self._exchange is None:
            raise RuntimeError("RabbitMQCrmEvents not started")
        message = aio_pika.Message(
            body=json.dumps(body).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=routing_key)
