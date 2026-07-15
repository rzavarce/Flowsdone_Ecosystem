import asyncpg
import logging

logger = logging.getLogger("idempotency.repo")


class PostgresIdempotencyRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def try_start(self, message_id, workflow_id) -> bool:
        query = """
        INSERT INTO workflow_executions (message_id, workflow_id, status)
        VALUES ($1, $2, 'processing')
        ON CONFLICT (message_id) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, str(message_id), str(workflow_id))
            return result.endswith("INSERT 0 1")

    async def mark_completed(self, message_id) -> None:
        query = """
        UPDATE workflow_executions
        SET status = 'completed', updated_at = now()
        WHERE message_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, str(message_id))

    async def mark_failed(self, message_id) -> None:
        query = """
        UPDATE workflow_executions
        SET status = 'failed', updated_at = now()
        WHERE message_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, str(message_id))