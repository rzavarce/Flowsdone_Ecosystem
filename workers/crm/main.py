"""CRM worker: delivers queued CRM handoff events (handoff.started,
message.inbound, handoff.expired) to each client's CRM, retrying
transient failures and parking the rest in the dead-letter queue.
"""

import asyncio
import json
import logging
from pathlib import Path

from app.adapters.inbound.queue.rabbitmq_consumer import RabbitMQConsumer
from app.adapters.outbound.crm.factory import CrmProviderFactory
from app.adapters.outbound.db.crm_repositories import SqlAlchemyCrmIntegrationRepository
from app.adapters.outbound.http.callback_sender import build_callback_sender
from app.adapters.outbound.queue.rabbitmq_crm_events import RabbitMQCrmEvents
from app.application.use_cases.deliver_crm_event import DeliverCrmEventUseCase
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.domain.models.crm import CrmEvent
from app.infrastructure.database import create_engine, create_sessionmaker
from workers.heartbeat import heartbeat_forever

setup_logging(settings.LOG_LEVEL)
setup_tracing()
logger = logging.getLogger("crm.worker")

# Checked by the docker-compose healthcheck (see workers/heartbeat.py).
HEARTBEAT_FILE = Path("/tmp/crm-worker.heartbeat")


async def main() -> None:
    """Wire up dependencies and consume the CRM event queue until stopped."""
    engine = create_engine()
    queue = RabbitMQCrmEvents(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_CRM_EXCHANGE,
        routing_key=settings.RABBITMQ_CRM_ROUTING_KEY,
        queue_name=settings.RABBITMQ_CRM_QUEUE,
        dead_queue_name=settings.RABBITMQ_CRM_DEAD_QUEUE,
    )
    await queue.start()

    deliver = DeliverCrmEventUseCase(
        integrations=SqlAlchemyCrmIntegrationRepository(create_sessionmaker(engine)),
        providers=CrmProviderFactory().build_all(ensure_allowed=build_callback_sender(settings).ensure_allowed),
        dead_letters=queue,
        max_attempts=settings.CRM_DELIVERY_MAX_ATTEMPTS,
        backoff_seconds=settings.CRM_DELIVERY_BACKOFF_SECONDS,
    )

    async def handler(body: bytes) -> None:
        """Deliver one queued event.

        Args:
            body (bytes): The raw message body (a CrmEvent as JSON).
        """
        try:
            event = CrmEvent.model_validate(json.loads(body))
        except Exception:
            logger.error("crm.worker.invalid_message", extra={"body": body.decode("utf-8", errors="ignore")[:500]})
            return
        await deliver.execute(event)

    consumer = RabbitMQConsumer(
        url=settings.RABBITMQ_URL,
        exchange_name=settings.RABBITMQ_CRM_EXCHANGE,
        queue_name=settings.RABBITMQ_CRM_QUEUE,
        routing_key=settings.RABBITMQ_CRM_ROUTING_KEY,
    )

    heartbeat = asyncio.create_task(heartbeat_forever(HEARTBEAT_FILE))
    try:
        await consumer.start(handler)
    finally:
        heartbeat.cancel()
        await queue.stop()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("crm.worker.stopped")
