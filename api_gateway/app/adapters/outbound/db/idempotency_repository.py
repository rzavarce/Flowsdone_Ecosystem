"""Raw-asyncpg implementation of IdempotencyRepositoryPort."""

import logging

import asyncpg

logger = logging.getLogger("idempotency.repo")


class PostgresIdempotencyRepository:
    """Tracks workflow execution state in the `workflow_executions` table
    using raw asyncpg (not SQLAlchemy) for minimal per-message overhead
    in the hot path.
    """

    def __init__(self, pool: asyncpg.Pool):
        """Build the repository.

        Args:
            pool (asyncpg.Pool): Connection pool used to run queries.
        """
        self.pool = pool

    async def try_start(self, message_id, workflow_id) -> bool:
        """Attempt to claim a message for processing.

        Inserts a "processing" row; relies on the message_id primary
        key to make the claim atomic across concurrent workers.

        Args:
            message_id (str): Unique id of the message being processed.
            workflow_id (str): Id of the workflow that will process it.

        Returns:
            bool: True if this call inserted the row (processing should
            proceed); False if it already existed (duplicate).
        """
        query = """
        INSERT INTO workflow_executions (message_id, workflow_id, status)
        VALUES ($1, $2, 'processing')
        ON CONFLICT (message_id) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, str(message_id), str(workflow_id))
            return result.endswith("INSERT 0 1")

    async def mark_completed(self, message_id) -> None:
        """Mark a message's execution as completed.

        Args:
            message_id (str): Unique id of the message.
        """
        query = """
        UPDATE workflow_executions
        SET status = 'completed', updated_at = now()
        WHERE message_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, str(message_id))

    async def mark_failed(self, message_id) -> None:
        """Mark a message's execution as failed, allowing a retry.

        Args:
            message_id (str): Unique id of the message.
        """
        query = """
        UPDATE workflow_executions
        SET status = 'failed', updated_at = now()
        WHERE message_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, str(message_id))
