"""Redis implementation of LoginThrottlePort (fixed-window counters)."""

from __future__ import annotations

from redis.asyncio import Redis

_PREFIX = "auth:throttle:"


class RedisLoginThrottle:
    """Counts failed logins per key with a fixed window that starts at
    the first failure and expires on its own.
    """

    def __init__(self, client: Redis) -> None:
        """Build the throttle.

        Args:
            client (Redis): An async Redis client (`decode_responses=True`).
        """
        self._client = client

    async def failures(self, key: str) -> int:
        """Current failure count for a key.

        Args:
            key (str): Bucket key.

        Returns:
            int: Failures in the active window (0 if none).
        """
        raw = await self._client.get(_PREFIX + key)
        return int(raw) if raw is not None else 0

    async def record_failure(self, key: str, *, window_seconds: int) -> int:
        """Count a failure; the window starts at the first failure.

        Args:
            key (str): Bucket key.
            window_seconds (int): Window after which the count resets.

        Returns:
            int: The new failure count.
        """
        count = await self._client.incr(_PREFIX + key)
        if count == 1:
            await self._client.expire(_PREFIX + key, window_seconds)
        return int(count)

    async def reset(self, key: str) -> None:
        """Clear a bucket.

        Args:
            key (str): Bucket key.
        """
        await self._client.delete(_PREFIX + key)
