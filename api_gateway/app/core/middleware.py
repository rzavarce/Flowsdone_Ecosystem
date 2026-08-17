"""HTTP middleware for request correlation id propagation and access logging."""

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from api_gateway.app.core.context import correlation_id_ctx

logger = logging.getLogger("api")

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagates or generates a correlation id for each request, sets it
    in the async context for the duration of the request (so log lines
    can be correlated), echoes it back in the response header, and logs
    the request outcome and latency.

    Not currently registered in main.py (only the no_cache_static
    middleware is), so correlation ids from this class are not
    actually attached to requests yet.
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

        correlation_id = (
            request.headers.get(CORRELATION_HEADER)
            or str(uuid.uuid4())
        )

        token = correlation_id_ctx.set(correlation_id)

        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)

        latency_ms = (time.perf_counter() - start_time) * 1000

        response.headers[CORRELATION_HEADER] = correlation_id

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
