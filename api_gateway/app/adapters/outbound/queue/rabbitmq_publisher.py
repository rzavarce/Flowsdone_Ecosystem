import json
import logging
from typing import Any

import aio_pika

from ....domain.ports.outbound import MessagePublisherPort

logger = logging.getLogger("rabbitmq.publisher")


class RabbitMQPublisher(MessagePublisherPort):
    """
    Outbound adapter for publishing messages to RabbitMQ.
    """

    def __init__(
        self,
        *,
        url: str,
        exchange_name: str,
        routing_key: str,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._routing_key = routing_key

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self) -> None:
        logger.info(
            "rabbitmq.publisher.starting",
            extra={
                "exchange": self._exchange_name,
                "routing_key": self._routing_key,
            },
        )

        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        logger.info(
            "rabbitmq.publisher.ready",
            extra={"exchange": self._exchange_name},
        )

    async def stop(self) -> None:
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()

        logger.info("rabbitmq.publisher.stopped")

    async def publish(self, event: Any) -> None:
        if not self._exchange:
            raise RuntimeError("RabbitMQPublisher not started")

        payload = json.dumps(event, default=str).encode("utf-8")

        message = aio_pika.Message(
            body=payload,
            content_type="application/json",
        )

        await self._exchange.publish(
            message,
            routing_key=self._routing_key,
        )

        logger.info(
            "rabbitmq.message.published",
            extra={
                "exchange": self._exchange_name,
                "routing_key": self._routing_key,
            },
        )
