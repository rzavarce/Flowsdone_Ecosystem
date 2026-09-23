"""Redis implementation of QuotaCounterPort: one hash per tenant and
month (field = channel type), plus one-off markers for alerts.
"""

from __future__ import annotations

from typing import Dict, Optional
from uuid import UUID

from redis.asyncio import Redis

from app.domain.ports.outbound import QuotaCounterPort

_COUNTER_PREFIX = "billing:quota:"
_ONCE_PREFIX = "billing:once:"
# A month's counters/markers outlive the month a bit (late messages,
# statements) and then expire on their own.
_TTL_SECONDS = 40 * 24 * 3600


def _key(tenant_id: UUID, period: str) -> str:
    """Redis key of a tenant's counters for a period.

    Args:
        tenant_id (UUID): Tenant id.
        period (str): "YYYY-MM".

    Returns:
        str: The key.
    """
    return f"{_COUNTER_PREFIX}{tenant_id}:{period}"


class RedisQuotaCounter(QuotaCounterPort):
    """Live monthly counters of AI-handled messages in Redis."""

    def __init__(self, client: Redis) -> None:
        """Build the counter store.

        Args:
            client (Redis): An async Redis client (decode_responses=True).
        """
        self._client = client

    async def get_all(self, tenant_id: UUID, period: str) -> Optional[Dict[str, int]]:
        """This period's counters, or None if never initialized.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".

        Returns:
            Optional[Dict[str, int]]: Channel -> messages.
        """
        values = await self._client.hgetall(_key(tenant_id, period))
        if not values:
            return None
        return {_str(k): int(v) for k, v in values.items() if _str(k) != "__init__"}

    async def seed(self, tenant_id: UUID, period: str, counts: Dict[str, int]) -> None:
        """Initialize counters, keeping values already present.

        An "__init__" field marks the hash as initialized even when every
        count is 0, so it is not rebuilt on every message.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            counts (Dict[str, int]): Channel -> messages already used.
        """
        key = _key(tenant_id, period)
        await self._client.hsetnx(key, "__init__", 1)
        for channel, count in counts.items():
            await self._client.hsetnx(key, channel, count)
        await self._client.expire(key, _TTL_SECONDS)

    async def increment(self, tenant_id: UUID, period: str, channel_type: str, by: int = 1) -> int:
        """Add to a channel's counter.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            channel_type (str): Channel.
            by (int): Amount.

        Returns:
            int: The new value.
        """
        key = _key(tenant_id, period)
        value = await self._client.hincrby(key, channel_type, by)
        await self._client.expire(key, _TTL_SECONDS)
        return int(value)

    async def first_time(self, key: str) -> bool:
        """Atomically mark a one-off event.

        Args:
            key (str): Event key.

        Returns:
            bool: True only the first time.
        """
        return bool(await self._client.set(f"{_ONCE_PREFIX}{key}", 1, nx=True, ex=_TTL_SECONDS))


def _str(value) -> str:
    """Decode a Redis hash field (bytes or str).

    Args:
        value: Field name.

    Returns:
        str: The decoded name.
    """
    return value.decode() if isinstance(value, bytes) else value
