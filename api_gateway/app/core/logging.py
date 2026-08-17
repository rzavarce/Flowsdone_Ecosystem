"""JSON logging setup, with correlation id injection and optional OTel export."""

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.core.context import correlation_id_ctx


class CorrelationIdFilter(logging.Filter):
    """Injects the current request's correlation id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach correlation_id to the record and always let it through.

        Args:
            record (logging.LogRecord): The log record being emitted.

        Returns:
            bool: Always True; this filter only enriches records, it
            never suppresses them.
        """
        record.correlation_id = correlation_id_ctx.get()
        return True


def _otel_handler() -> logging.Handler | None:
    """Build an OTLP logging handler if OpenTelemetry export is enabled.

    Returns:
        logging.Handler | None: A configured handler, or None if
        OTEL_ENABLED is False or OTEL_EXPORTER_OTLP_ENDPOINT is not set.
    """
    if not settings.OTEL_ENABLED or not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return None

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    provider = LoggerProvider(
        resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    )
    exporter = OTLPLogExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/logs"
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(provider)

    handler = LoggingHandler(logger_provider=provider)
    handler.addFilter(CorrelationIdFilter())
    return handler


def setup_logging(level: str):
    """Configure the root logger for JSON output to stdout.

    Also attaches an OTLP handler when OpenTelemetry export is enabled.
    Every log record is enriched with the current correlation id.

    Args:
        level (str): Logging level name (e.g. "INFO", "DEBUG").
    """
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s"
    )

    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    handlers: list[logging.Handler] = [handler]

    otel_handler = _otel_handler()
    if otel_handler is not None:
        handlers.append(otel_handler)

    root.handlers = handlers
