"""Kafka inbound worker: runs Langflow workflows for inbound messages and
publishes their outbound response back to the same topic.
"""

import asyncio
import logging

import asyncpg

from app.adapters.inbound.queue.kafka_consumer import KafkaConsumer
from app.adapters.outbound.db.idempotency_repository import (
    PostgresIdempotencyRepository,
)
from app.adapters.outbound.langflow.executor import LangflowExecutor
from app.adapters.outbound.queue.kafka_publisher import KafkaPublisher
from app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.domain.models.message_envelope import MessageEnvelope
from app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
setup_tracing()
logger = logging.getLogger("kafka.inbound.worker")


async def main() -> None:
    """Wire up dependencies and consume KAFKA_TOPIC until stopped.

    For each inbound message: runs its Langflow workflow
    (ExecuteWorkflowUseCase, idempotent via Postgres), then publishes
    the outbound response back to the same topic
    (HandleOutboundResponseUseCase), to be picked up by
    kafka_outbound_worker.
    """
    logger.info(
        "kafka.inbound.worker.starting",
        extra={
            "topic": settings.KAFKA_TOPIC,
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        },
    )

    await ensure_topics_exist()

    # Database (idempotency)
    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL_ASYNC,
        min_size=1,
        max_size=5,
    )

    idempotency_repo = PostgresIdempotencyRepository(pool)

    # Langflow executor
    executor = LangflowExecutor()

    use_case = ExecuteWorkflowUseCase(
        idempotency_repo=idempotency_repo,
        executor=executor,
    )

    # Outbound publisher (responses)
    publisher = KafkaPublisher(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC,
    )
    await publisher.start()

    outbound_use_case = HandleOutboundResponseUseCase(publisher=publisher)

    async def handler(body: dict):
        """Process one Kafka message: run its workflow and publish the response.

        Args:
            body (dict): The decoded message body.

        Raises:
            Exception: Re-raised if the body cannot be parsed as a
                MessageEnvelope, so the message is not committed.
        """
        try:
            envelope = MessageEnvelope.parse(body)
        except Exception:
            logger.error(
                "Invalid Kafka message",
                extra={"body": str(body)},
            )
            raise

        if envelope.meta.direction != "inbound":
            return

        logger.info(
            "kafka.inbound.message.received",
            extra={
                "conversation_id": str(envelope.meta.conversation_id),
                "workflow_id": str(envelope.meta.workflow_id),
                "channel": envelope.channel,
            },
        )

        result = await use_case.execute(envelope)
        if not result:
            return

        await outbound_use_case.execute(envelope, result)

    consumer = KafkaConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC,
        group_id="workflow-workers",
    )

    await consumer.start(handler)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("kafka.inbound.worker.stopped")
