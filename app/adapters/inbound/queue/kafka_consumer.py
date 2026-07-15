import json
import logging
from typing import Callable, Awaitable

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("kafka.consumer")


class KafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
    ) -> None:
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
        logger.info(
            "kafka.consumer.starting",
            extra={
                "topic": self._topic,
                "group_id": self._consumer._group_id,
            },
        )

        await self._consumer.start()

        # LOOP INFINITO: el worker no debe terminar
        async for msg in self._consumer:
            try:
                await handler(msg.value)
                await self._consumer.commit()
            except Exception:
                # No rompemos el loop ni cerramos el consumer
                logger.exception("kafka.consumer.handler.failed")
