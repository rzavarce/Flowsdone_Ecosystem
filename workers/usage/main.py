"""Usage worker: periodic jobs of usage metering and billing.

- Imports LLM token usage from Langfuse into ClickHouse usage_events,
  attributed to the conversation (and tenant) of each trace.
- Closes the previous month's statements (checked hourly; idempotent,
  so it is a no-op once the month is closed).
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.adapters.outbound.clickhouse.usage_store import ClickHouseUsageStore
from app.adapters.outbound.db.billing_repositories import (
    SqlAlchemyPlanRepository,
    SqlAlchemyStatementRepository,
    SqlAlchemySubscriptionRepository,
)
from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.adapters.outbound.db.usage_repositories import (
    SqlAlchemyCostRateRepository,
    SqlAlchemySyncCursorRepository,
)
from app.adapters.outbound.langfuse.usage_source import LangfuseUsageSource
from app.application.use_cases.billing import CloseBillingPeriodUseCase, ComputeStatementUseCase
from app.application.use_cases.sync_llm_usage import SyncLlmUsageUseCase
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.domain.models.billing import previous_period
from app.infrastructure.database import create_engine, create_sessionmaker
from workers.heartbeat import every, heartbeat_forever

setup_logging(settings.LOG_LEVEL)
setup_tracing()
logger = logging.getLogger("usage.worker")

# Checked by the docker-compose healthcheck (see workers/heartbeat.py).
HEARTBEAT_FILE = Path("/tmp/usage-worker.heartbeat")
CLOSE_PERIOD_INTERVAL_SECONDS = 3600


async def main() -> None:
    """Wire up dependencies and run the periodic jobs forever."""
    logger.info("usage.worker.starting")

    engine = create_engine()
    sessionmaker = create_sessionmaker(engine)
    clickhouse = ClickHouseHttpClient(
        base_url=settings.CLICKHOUSE_URL,
        database=settings.CLICKHOUSE_DATABASE,
        user=settings.CLICKHOUSE_APP_USER,
        password=settings.CLICKHOUSE_APP_PASSWORD,
    )
    usage_store = ClickHouseUsageStore(clickhouse)
    conversation_repo = SqlAlchemyConversationRepository(sessionmaker)
    closeables = [clickhouse]

    subscriptions = SqlAlchemySubscriptionRepository(sessionmaker)
    statements = SqlAlchemyStatementRepository(sessionmaker)
    close_period = CloseBillingPeriodUseCase(
        compute=ComputeStatementUseCase(
            usage_store=usage_store,
            cost_rates=SqlAlchemyCostRateRepository(sessionmaker),
            plans=SqlAlchemyPlanRepository(sessionmaker),
            subscriptions=subscriptions,
            statements=statements,
        ),
        subscriptions=subscriptions,
        statements=statements,
    )

    async def close_previous_month() -> None:
        """Close last month's statements once its grace period is over
        (no-op once closed)."""
        now = datetime.now(timezone.utc)
        period = previous_period(now.date())
        if now >= close_period.closable_at(period):
            await close_period.execute(period=period, now=now)

    jobs = [
        asyncio.create_task(heartbeat_forever(HEARTBEAT_FILE)),
        asyncio.create_task(
            every(CLOSE_PERIOD_INTERVAL_SECONDS, close_previous_month, logger, "billing.period_close.failed")
        ),
    ]

    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        source = LangfuseUsageSource(
            base_url=settings.LANGFUSE_BASE_URL,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
        )
        closeables.append(source)
        sync = SyncLlmUsageUseCase(
            source=source,
            conversation_repo=conversation_repo,
            usage_store=usage_store,
            cursors=SqlAlchemySyncCursorRepository(sessionmaker),
        )
        jobs.append(
            asyncio.create_task(
                every(
                    settings.LLM_USAGE_SYNC_INTERVAL_SECONDS,
                    lambda: sync.execute(datetime.now(timezone.utc)),
                    logger,
                    "usage.llm_sync.failed",
                )
            )
        )
    else:
        logger.warning("usage.llm_sync.disabled", extra={"reason": "LANGFUSE_PUBLIC_KEY/SECRET_KEY not set"})

    try:
        await asyncio.gather(*jobs)
    finally:
        for job in jobs:
            job.cancel()
        for closeable in closeables:
            await closeable.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("usage.worker.stopped")
