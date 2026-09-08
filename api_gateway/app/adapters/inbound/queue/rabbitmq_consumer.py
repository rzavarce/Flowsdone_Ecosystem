"""Generic RabbitMQ consumer used by the inbound and outbound workers."""

import logging
from typing import Awaitable, Callable

import aio_pika

logger = logging.getLogger("rabbit.consumer")


class RabbitMQConsumer:
    """Consumes messages from a RabbitMQ topic exchange/queue and
    dispatches them to a handler, using aio_pika's automatic ack/nack
    via `message.process()`.
    """

    def __init__(
        self,
        *,
        url: str,
        exchange_name: str,
        queue_name: str,
        routing_key: str,
    ) -> None:
        """Build the consumer.

        Args:
            url (str): RabbitMQ connection URL.
            exchange_name (str): Topic exchange to declare and consume from.
            queue_name (str): Queue to declare and bind.
            routing_key (str): Routing key to bind the queue with.
        """
        self._url = url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._routing_key = routing_key

    async def start(
        self,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Declare the exchange/queue, bind them, and consume forever.

        Args:
            handler (Callable[[dict], Awaitable[None]]): Async callback
                invoked with each message's raw body.
        """
        logger.info(
            "rabbit.consumer.starting",
            extra={
                "exchange": self._exchange_name,
                "queue": self._queue_name,
                "routing_key": self._routing_key,
            },
        )

        connection = await aio_pika.connect_robust(self._url)
        channel = await connection.channel()

        exchange = await channel.declare_exchange(
            self._exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        queue = await channel.declare_queue(
            self._queue_name,
            durable=True,
        )

        await queue.bind(exchange, routing_key=self._routing_key)

        logger.info("rabbit.consumer.ready")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await handler(message.body)
