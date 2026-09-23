"""Conversations worker: archives recorded conversation messages into
ClickHouse (plus the channel/platform usage they represent), and
periodically closes conversations whose contact never came back
(inactivity window / maximum duration).
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.adapters.inbound.queue.kafka_batch_consumer import KafkaBatchConsumer
from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.adapters.outbound.clickhouse.message_archive import ClickHouseMessageArchive
from app.adapters.outbound.clickhouse.usage_store import ClickHouseUsageStore
from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.adapters.outbound.session.postgres_session_history_repository import (
    PostgresSessionHistoryRepository,
)
from app.application.use_cases.archive_conversation_messages import ArchiveConversationMessagesUseCase
from app.application.use_cases.close_expired_conversations import CloseExpiredConversationsUseCase
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.domain.models.conversation import ConversationLifecyclePolicy
from app.infrastructure.database import create_engine, create_sessionmaker
from app.infrastructure.kafka_admin import ensure_topics_exist
from workers.heartbeat import every, heartbeat_forever

setup_logging(settings.LOG_LEVEL)
setup_tracing()
logger = logging.getLogger("kafka.conversations.worker")

# Checked by the docker-compose healthcheck (see workers/heartbeat.py).
HEARTBEAT_FILE = Path("/tmp/conversations-worker.heartbeat")


async def main() -> None:
    """Wire up dependencies, then run the archiver and the sweeper."""
    logger.info(
        "kafka.conversations.worker.starting",
        extra={"topic": settings.CONVERSATION_EVENTS_TOPIC, "clickhouse_url": settings.CLICKHOUSE_URL},
    )

    await ensure_topics_exist()

    engine = create_engine()
    sessionmaker = create_sessionmaker(engine)
    policy = ConversationLifecyclePolicy(
        inactivity=timedelta(seconds=settings.CONVERSATION_INACTIVITY_SECONDS),
        max_duration=timedelta(seconds=settings.CONVERSATION_MAX_DURATION_SECONDS),
    )
    sweep = CloseExpiredConversationsUseCase(
        conversation_repo=SqlAlchemyConversationRepository(sessionmaker),
        session_history_repo=PostgresSessionHistoryRepository(sessionmaker),
        policy=policy,
    )

    clickhouse = ClickHouseHttpClient(
        base_url=settings.CLICKHOUSE_URL,
        database=settings.CLICKHOUSE_DATABASE,
        user=settings.CLICKHOUSE_APP_USER,
        password=settings.CLICKHOUSE_APP_PASSWORD,
    )
    archive_messages = ArchiveConversationMessagesUseCase(
        archive=ClickHouseMessageArchive(clickhouse),
        retention=timedelta(days=settings.MESSAGE_RETENTION_DAYS),
        usage_store=ClickHouseUsageStore(clickhouse),
    )

    consumer = KafkaBatchConsumer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        topic=settings.CONVERSATION_EVENTS_TOPIC,
        group_id="conversation-archivers",
    )

    background = [
        # A failed sweep is retried next tick; it never stops archiving.
        asyncio.create_task(
            every(
                settings.CONVERSATION_SWEEP_INTERVAL_SECONDS,
                lambda: sweep.execute(datetime.now(timezone.utc)),
                logger,
                "conversations.sweep.failed",
            )
        ),
        asyncio.create_task(heartbeat_forever(HEARTBEAT_FILE)),
    ]
    try:
        await consumer.start(archive_messages.execute)
    finally:
        for task in background:
            task.cancel()
        await clickhouse.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("kafka.conversations.worker.stopped")
