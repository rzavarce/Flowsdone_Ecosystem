import logging
from typing import Callable, Awaitable

import aio_pika

logger = logging.getLogger("rabbit.consumer")


class RabbitMQConsumer:
    def __init__(
        self,
        *,
        url: str,
        exchange_name: str,
        queue_name: str,
        routing_key: str,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._routing_key = routing_key

    async def start(
        self,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
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
