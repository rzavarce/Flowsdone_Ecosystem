import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from app.domain.ports.outbound import MessagePublisherPort

logger = logging.getLogger("kafka.publisher")


class KafkaPublisher(MessagePublisherPort):
    """
    Outbound adapter for publishing messages to Kafka.

    Responsibilities:
    - Connect to Kafka
    - Serialize events
    - Publish them to a configured topic
    """

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers
        )
        await self._producer.start()

        logger.info(
            "kafka.publisher.started",
            extra={
                "topic": self._topic,
                "bootstrap_servers": self._bootstrap_servers,
            },
        )

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("kafka.publisher.stopped", extra={"topic": self._topic})

    async def publish(self, event: Any) -> None:
        if not self._producer:
            raise RuntimeError("Kafka producer not started")

        payload = json.dumps(event, default=str).encode("utf-8")

        await self._producer.send_and_wait(
            topic=self._topic,
            value=payload,
        )

        logger.info(
            "kafka.message.published",
            extra={"topic": self._topic},
        )
