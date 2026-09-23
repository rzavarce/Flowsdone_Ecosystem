"""Liveness heartbeat shared by the long-running workers: a file touched
periodically while the event loop runs, checked by the docker-compose
healthcheck (stale file -> unhealthy).
"""

import asyncio
from pathlib import Path

HEARTBEAT_INTERVAL_SECONDS = 30


async def heartbeat_forever(path: Path, interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS) -> None:
    """Touch `path` every `interval_seconds`, forever.

    Args:
        path (Path): Heartbeat file.
        interval_seconds (int): Pause between touches.
    """
    while True:
        path.touch()
        await asyncio.sleep(interval_seconds)


async def every(interval_seconds: int, job, logger, event: str) -> None:
    """Run `job()` every `interval_seconds`, forever; a failing run is
    logged (as `event`) and retried on the next tick, never propagated.

    Args:
        interval_seconds (int): Pause between runs.
        job: Zero-argument async callable.
        logger: Logger for failures.
        event (str): Log event name for a failed run.
    """
    while True:
        try:
            await job()
        except Exception:
            logger.exception(event)
        await asyncio.sleep(interval_seconds)
