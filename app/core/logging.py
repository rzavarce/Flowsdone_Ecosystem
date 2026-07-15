import logging
import sys
from pythonjsonlogger import jsonlogger
from app.core.context import correlation_id_ctx
from app.core.config import settings


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx.get()
        return True


def _otel_handler() -> logging.Handler | None:
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
