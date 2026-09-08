"""OpenTelemetry trace setup: exports spans via OTLP when enabled.

Complements core/logging.py, which handles the logs signal. This
module handles traces: a global TracerProvider exporting to
OTEL_EXPORTER_OTLP_ENDPOINT, plus automatic instrumentation of
outgoing httpx calls (Langflow, Evolution, Meta, Telegram, ...) and,
for the gateway, incoming FastAPI requests.
"""

import logging

from app.core.config import settings

logger = logging.getLogger("bootstrap")


def setup_tracing() -> None:
    """Configure the global OpenTelemetry tracer provider and instrument
    outgoing HTTP calls made via httpx.

    No-ops when OTEL_ENABLED is False or OTEL_EXPORTER_OTLP_ENDPOINT is
    unset, so calling this is always safe regardless of environment.
    Safe to call more than once per process: httpx instrumentation
    is idempotent, and re-registering the tracer provider is harmless
    since every caller in this codebase configures it identically.
    """
    if not settings.OTEL_ENABLED or not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if not HTTPXClientInstrumentor().is_instrumented_by_opentelemetry:
        HTTPXClientInstrumentor().instrument()

    logger.info("tracing.otel.enabled", extra={"service_name": settings.OTEL_SERVICE_NAME})


def instrument_fastapi_app(app) -> None:
    """Instrument a FastAPI app so each incoming HTTP request gets a
    root trace span.

    No-ops under the same conditions as setup_tracing(). Call this
    once, after the FastAPI app is constructed (only the gateway
    serves HTTP directly; workers have nothing to instrument here).

    Args:
        app: The FastAPI application instance to instrument.
    """
    if not settings.OTEL_ENABLED or not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
