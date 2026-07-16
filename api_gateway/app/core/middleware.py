import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from api_gateway.app.core.context import correlation_id_ctx
import logging

logger = logging.getLogger("api")

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        correlation_id = (
            request.headers.get(CORRELATION_HEADER)
            or str(uuid.uuid4())
        )

        # Set en contexto async
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