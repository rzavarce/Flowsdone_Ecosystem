"""Health endpoints for the docker-compose healthcheck and the deploy.

- `GET /health`: liveness. The process answers HTTP; no dependency is
  touched, so a slow database never makes Docker restart the gateway.
- `GET /ready`: readiness. Postgres and Redis answer within a short
  timeout. 503 if one doesn't. Only "ok"/"fail" per dependency is returned,
  never errors, hosts or versions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from fastapi import APIRouter, Request
from sqlalchemy import text
from starlette.responses import JSONResponse

logger = logging.getLogger("http.health")

router = APIRouter(tags=["health"])

# Each dependency must answer within this, so /ready never hangs a probe.
CHECK_TIMEOUT_SECONDS = 2.0


@router.get("/health")
async def health() -> Dict[str, str]:
    """Liveness: the gateway process is up and serving requests.

    Returns:
        Dict[str, str]: `{"status": "ok"}`.
    """
    return {"status": "ok"}


async def _check(name: str, probe: Callable[[], Awaitable[Any]]) -> str:
    """Run one dependency probe with a timeout.

    Args:
        name (str): Dependency name, for the log.
        probe (Callable[[], Awaitable[Any]]): Zero-argument coroutine factory.

    Returns:
        str: "ok", or "fail" if it raised or timed out (details only logged).
    """
    try:
        await asyncio.wait_for(probe(), timeout=CHECK_TIMEOUT_SECONDS)
        return "ok"
    except Exception:
        logger.warning("health.dependency_failed", extra={"dependency": name}, exc_info=True)
        return "fail"


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness: the gateway can reach Postgres and Redis.

    Args:
        request (Request): Used to reach `app.state.db_engine` and
            `app.state.redis_client`.

    Returns:
        JSONResponse: 200 `{"status": "ok", "checks": {...}}` when every
        dependency answers; 503 with `"status": "fail"` otherwise. A
        dependency the gateway runs without is reported as "skipped".
    """
    state = request.app.state
    checks: Dict[str, str] = {}

    engine = getattr(state, "db_engine", None)
    if engine is None:
        checks["database"] = "skipped"
    else:

        async def database() -> None:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

        checks["database"] = await _check("database", database)

    redis_client = getattr(state, "redis_client", None)
    checks["redis"] = "skipped" if redis_client is None else await _check("redis", redis_client.ping)

    healthy = all(v != "fail" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "fail", "checks": checks},
    )
