"""HTTP middleware for request correlation id propagation and access logging."""

import logging
import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.context import correlation_id_ctx

logger = logging.getLogger("api")

CORRELATION_HEADER = "X-Correlation-ID"
# A client-supplied id ends up in every log line of the request, so only
# short, plain ids are trusted; anything else is replaced with a new one.
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
# Polled by the Docker/deploy healthchecks every few seconds: not logged.
_UNLOGGED_PATHS = frozenset({"/health", "/ready"})


def _correlation_id_from(header_value: str | None) -> str:
    """Pick the request's correlation id.

    Args:
        header_value (str | None): Value of the X-Correlation-ID header.

    Returns:
        str: The header value if it is a short, plain id; a new UUID4
        otherwise.
    """
    if header_value and _VALID_CORRELATION_ID.match(header_value):
        return header_value
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagates or generates a correlation id for each request, sets it
    in the async context for the duration of the request (so log lines
    can be correlated), echoes it back in the response header, and logs
    the request outcome and latency (except for the healthcheck paths).
    """

    async def dispatch(self, request: Request, call_next):
        """Process a request, wrapping it with correlation id tracking.

        Args:
            request (Request): The incoming request.
            call_next: The next handler in the middleware chain.

        Returns:
            Response: The response, with the correlation id header set.
        """
        start_time = time.perf_counter()

        correlation_id = _correlation_id_from(request.headers.get(CORRELATION_HEADER))

        token = correlation_id_ctx.set(correlation_id)

        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)

        latency_ms = (time.perf_counter() - start_time) * 1000

        response.headers[CORRELATION_HEADER] = correlation_id

        if request.url.path in _UNLOGGED_PATHS:
            return response

        logger.info(
            "request.completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
            },
        )

        return response
