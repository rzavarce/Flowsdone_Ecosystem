"""RabbitMQ inbound worker: runs Langflow workflows for inbound messages
and publishes their outbound response to the outbound exchange.
"""

import asyncio
import logging

import asyncpg

from app.adapters.inbound.queue.rabbitmq_consumer import RabbitMQConsumer
from app.adapters.outbound.db.idempotency_repository import (
    PostgresIdempotencyRepository,
)
from app.adapters.outbound.langflow.executor import LangflowExecutor
from app.adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher
from app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from app.application.use_cases.handle_outbound_response import (
    HandleOutboundResponseUseCase,
)
from app.core.config import settings
from app.core.logging import setup_logging
from app.domain.models.message_envelope import MessageEnvelope

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("rabbitmq.inbound.worker")


async def main() -> None:
    """Wire up dependencies and consume the inbound queue until stopped.

    For each inbound message: runs its Langflow workflow
    (ExecuteWorkflowUseCase, idempotent via Postgres), then publishes
    the outbound response to the RabbitMQ outbound exchange
    (HandleOutboundResponseUseCase), to be picked up by
    rabbitmq_outbound_worker.
    """
    logger.info(
        "rabbitmq.inbound.worker.starting",
        extra={
            "exchange": settings.RABBITMQ_EXCHANGE,
            "queue": settings.RABBITMQ_QUEUE,
            "routing_key": settings.RABBITMQ_ROUTING_KEY,
        },
    )

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

    # Publisher (for responses)
    publisher = RabbitMQPublisher(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_OUTBOUND_EXCHANGE,
        routing_key=settings.RABBITMQ_OUTBOUND_ROUTING_KEY,
    )

    await publisher.start()

    outbound_use_case = HandleOutboundResponseUseCase(
        publisher=publisher
    )

    async def handler(body: bytes) -> None:
        """Process one RabbitMQ message: run its workflow and publish the response.

        Args:
            body (bytes): The raw message body.
        """
        try:
            envelope = MessageEnvelope.parse(body)
        except Exception:
            logger.error(
                "Invalid RabbitMQ message",
                extra={"body": body.decode("utf-8", errors="ignore")},
            )
            return

        direction = getattr(envelope.meta, "direction", "inbound")

        if direction != "inbound":
            logger.debug(
                "rabbitmq.inbound.non_inbound_message_ignored",
                extra={
                    "message_id": str(envelope.meta.message_id),
                    "direction": direction,
                },
            )
            return

        logger.info(
            "rabbitmq.inbound.message.received",
            extra={
                "conversation_id": getattr(envelope.meta, "conversation_id", None),
                "workflow_id": getattr(envelope.meta, "workflow_id", None),
            },
        )

        result = await use_case.execute(envelope)

        if not result:
            logger.warning(
                "rabbitmq.inbound.no_result",
                extra={"message_id": str(envelope.meta.message_id)},
            )
            return

        # Handles the callback_url call and the outbound broker publish.
        await outbound_use_case.execute(envelope, result)

    consumer = RabbitMQConsumer(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_EXCHANGE,
        queue_name=settings.RABBITMQ_QUEUE,
        routing_key=settings.RABBITMQ_ROUTING_KEY,
    )

    await consumer.start(handler)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("rabbitmq.inbound.worker.stopped")
