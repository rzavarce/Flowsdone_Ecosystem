"""Generic Kafka consumer used by the inbound and outbound workers."""

import json
import logging
from typing import Awaitable, Callable

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("kafka.consumer")


class KafkaConsumer:
    """Consumes JSON messages from a Kafka topic and dispatches them to
    a handler, committing manually after each successful call.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
    ) -> None:
        """Build the consumer.

        Args:
            bootstrap_servers (str): Kafka bootstrap servers.
            topic (str): Topic to consume from.
            group_id (str): Consumer group id.
        """
        self._topic = topic
        self._consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )

    async def start(
        self,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        """Start consuming and run forever, dispatching each message.

        Commits the offset only after the handler succeeds. If the
        handler raises, the exception is logged and the loop continues
        without committing or closing the consumer, so the message can
        be retried after a restart.

        Args:
            handler (Callable[[dict], Awaitable[None]]): Async callback
                invoked with each decoded message.
        """
        logger.info(
            "kafka.consumer.starting",
            extra={
                "topic": self._topic,
                "group_id": self._consumer._group_id,
            },
        )

        await self._consumer.start()

        # This loop must run for the lifetime of the worker.
        async for msg in self._consumer:
            try:
                await handler(msg.value)
                await self._consumer.commit()
            except Exception:
                # Do not break the loop or close the consumer on a
                # handler failure; the message will be redelivered.
                logger.exception("kafka.consumer.handler.failed")
