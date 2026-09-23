"""Kafka consumer that hands messages to its handler in batches - for
sinks such as ClickHouse that want few large inserts rather than one
insert per message.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, List

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger("kafka.batch_consumer")


class KafkaBatchConsumer:
    """Consumes JSON messages in batches and commits offsets only after
    the handler has processed the whole batch.

    If the handler raises, nothing is committed: the consumer seeks back
    to the last committed offsets and retries the same messages after a
    backoff, so a sink outage delays archiving but never loses messages.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        max_records: int = 500,
        max_wait_ms: int = 2000,
        retry_backoff_seconds: float = 5.0,
    ) -> None:
        """Build the consumer.

        Args:
            bootstrap_servers (str): Kafka bootstrap servers.
            topic (str): Topic to consume from.
            group_id (str): Consumer group id.
            max_records (int): Maximum messages per batch.
            max_wait_ms (int): How long to wait for a batch to fill.
            retry_backoff_seconds (float): Pause before retrying a failed batch.
        """
        self._topic = topic
        self._max_records = max_records
        self._max_wait_ms = max_wait_ms
        self._retry_backoff_seconds = retry_backoff_seconds
        self._consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=_decode,
        )

    async def start(self, handler: Callable[[List[Any]], Awaitable[None]]) -> None:
        """Start consuming and run forever, dispatching each batch.

        Args:
            handler (Callable[[List[Any]], Awaitable[None]]): Async
                callback invoked with the decoded messages of a batch
                (undecodable messages arrive as None).
        """
        logger.info("kafka.batch_consumer.starting", extra={"topic": self._topic})
        await self._consumer.start()
        try:
            while True:
                batches = await self._consumer.getmany(
                    timeout_ms=self._max_wait_ms, max_records=self._max_records
                )
                values = [record.value for records in batches.values() for record in records]
                if not values:
                    continue
                try:
                    await handler(values)
                    await self._consumer.commit()
                except Exception:
                    logger.exception("kafka.batch_consumer.handler.failed", extra={"size": len(values)})
                    await self._rewind(list(batches.keys()))
                    await asyncio.sleep(self._retry_backoff_seconds)
        finally:
            await self._consumer.stop()

    async def _rewind(self, partitions: List[Any]) -> None:
        """Seek the given partitions back to their last committed offset
        (or the beginning, if none) so the failed batch is read again.

        Args:
            partitions (List[Any]): The TopicPartitions of the failed batch.
        """
        for partition in partitions:
            committed = await self._consumer.committed(partition)
            if committed is None:
                await self._consumer.seek_to_beginning(partition)
            else:
                self._consumer.seek(partition, committed)


def _decode(value: bytes) -> Any:
    """Decode a message value as JSON, or None if it is not valid JSON.

    Args:
        value (bytes): Raw message value.

    Returns:
        Any: The decoded value, or None.
    """
    try:
        return json.loads(value.decode("utf-8"))
    except Exception:
        logger.error("kafka.batch_consumer.undecodable_message")
        return None
