import asyncio
import logging

import asyncpg

from app.core.config import settings
from app.core.logging import setup_logging

from app.adapters.inbound.queue.rabbitmq_consumer import RabbitMQConsumer
from app.adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher

from app.adapters.outbound.langflow.executor import LangflowExecutor
from app.adapters.outbound.db.idempotency_repository import (
    PostgresIdempotencyRepository,
)

from app.application.use_cases.execute_workflow import ExecuteWorkflowUseCase
from app.application.use_cases.handle_outbound_response import (
    HandleOutboundResponseUseCase,
)

from app.domain.models.message_envelope import MessageEnvelope

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("rabbitmq.inbound.worker")


# ---------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------

async def main() -> None:
    logger.info(
        "rabbitmq.inbound.worker.starting",
        extra={
            "exchange": settings.RABBITMQ_EXCHANGE,
            "queue": settings.RABBITMQ_QUEUE,
            "routing_key": settings.RABBITMQ_ROUTING_KEY,
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
    # Publisher (para respuestas)
    # --------------------------------------------------------------
    
    publisher = RabbitMQPublisher(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_OUTBOUND_EXCHANGE,
        routing_key=settings.RABBITMQ_OUTBOUND_ROUTING_KEY,
    )

    await publisher.start()

    # ✅ Use case de salida (callback + publish)
    outbound_use_case = HandleOutboundResponseUseCase(
        publisher=publisher
    )

    # --------------------------------------------------------------
    # Handler
    # --------------------------------------------------------------
    async def handler(body: bytes) -> None:

        try:
            envelope = MessageEnvelope.parse(body)
        except Exception:
            logger.error(
                "Invalid RabbitMQ message",
                extra={"body": body.decode("utf-8", errors="ignore")},
            )
            return

        # ✅ Safe access
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

        # ----------------------------------------------------------
        # Ejecutar workflow (Langflow)
        # ----------------------------------------------------------
        result = await use_case.execute(envelope)

        if not result:
            logger.warning(
                "rabbitmq.inbound.no_result",
                extra={"message_id": str(envelope.meta.message_id)},
            )
            return

        # ----------------------------------------------------------
        # Manejo de respuesta (✅ AQUÍ VA TODO)
        # - callback_url
        # - publicación en Rabbit
        # ----------------------------------------------------------
        await outbound_use_case.execute(envelope, result)

    # --------------------------------------------------------------
    # RabbitMQ consumer
    # --------------------------------------------------------------
    consumer = RabbitMQConsumer(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_EXCHANGE,
        queue_name=settings.RABBITMQ_QUEUE,
        routing_key=settings.RABBITMQ_ROUTING_KEY,
    )

    await consumer.start(handler)


# ---------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("rabbitmq.inbound.worker.stopped")
