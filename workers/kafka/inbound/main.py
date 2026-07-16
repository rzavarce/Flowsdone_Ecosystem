import asyncio
import logging

import asyncpg

from api_gateway.app.core.config import settings
from api_gateway.app.core.logging import setup_logging

from api_gateway.app.adapters.inbound.queue.kafka_consumer import KafkaConsumer
from api_gateway.app.adapters.outbound.queue.kafka_publisher import KafkaPublisher

from api_gateway.app.adapters.outbound.langflow.executor import LangflowExecutor
from api_gateway.app.adapters.outbound.db.idempotency_repository import (
    PostgresIdempotencyRepository,
)

from api_gateway.app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from api_gateway.app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from api_gateway.app.domain.models.message_envelope import MessageEnvelope

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("kafka.inbound.worker")


# ---------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------

async def main() -> None:
    logger.info(
        "kafka.inbound.worker.starting",
        extra={
            "topic": settings.KAFKA_TOPIC,
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        },
    )

    # --------------------------------------------------------------
    # Database (idempotency)
    # --------------------------------------------------------------
    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL_ASYNC,
        min_size=1,
        max_size=5,
    )

    idempotency_repo = PostgresIdempotencyRepository(pool)

    # --------------------------------------------------------------
    # Langflow executor
    # --------------------------------------------------------------
    executor = LangflowExecutor()

    use_case = ExecuteWorkflowUseCase(
        idempotency_repo=idempotency_repo,
        executor=executor,
    )

    # --------------------------------------------------------------
    # Outbound publisher (responses)
    # --------------------------------------------------------------
    publisher = KafkaPublisher(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC,
    )
    await publisher.start()

    outbound_use_case = HandleOutboundResponseUseCase(publisher=publisher)

    # --------------------------------------------------------------
    # Handler
    # --------------------------------------------------------------

    async def handler(body: dict):
        try:
            envelope = MessageEnvelope.parse(body)
        except Exception as e:
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

    # --------------------------------------------------------------
    # Kafka consumer
    # --------------------------------------------------------------
    consumer = KafkaConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.KAFKA_TOPIC,
        group_id="workflow-workers",
    )

    await consumer.start(handler)


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("kafka.inbound.worker.stopped")