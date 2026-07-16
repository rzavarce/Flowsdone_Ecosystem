import os
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # --------------------------------------------------
    # Environment
    # --------------------------------------------------
    ENV: str = "local"
    LOG_LEVEL: str = "INFO"

    # --------------------------------------------------
    # Kafka
    # --------------------------------------------------
    ENABLE_KAFKA: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC: str = "inbound.messages"
    DLQ_TOPIC: str = "inbound.messages.dlq"

    # --------------------------------------------------
    # RabbitMQ
    # --------------------------------------------------
    ENABLE_RABBITMQ: bool = False
    RABBITMQ_URL: Optional[str] = None
    RABBITMQ_EXCHANGE: Optional[str] = None
    RABBITMQ_ROUTING_KEY: Optional[str] = None
    RABBITMQ_QUEUE: Optional[str] = None

    RABBITMQ_OUTBOUND_EXCHANGE: Optional[str] = None
    RABBITMQ_OUTBOUND_ROUTING_KEY: Optional[str] = None
    RABBITMQ_OUTBOUND_QUEUE: Optional[str] = None

    

    # --------------------------------------------------
    # Database (NO hard crash)
    # --------------------------------------------------
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_ASYNC: Optional[str] = None

    # --------------------------------------------------
    # Langflow
    # --------------------------------------------------
    LANGFLOW_BASE_URL: str = "http://langflow:7860"

    # --------------------------------------------------
    # Webhook callbacks
    # --------------------------------------------------
    CALLBACK_HMAC_SECRET: str = "dev-secret-change-me"
    CALLBACK_MAX_RETRIES: int = 3
    CALLBACK_BACKOFF_SECONDS: int = 2
    GATEWAY_INTERNAL_URL: str = "http://api:8000"

    # --------------------------------------------------
    # OpenTelemetry (logs + traces)
    # --------------------------------------------------
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = "fd-service"

    # --------------------------------------------------
    # Misc
    # --------------------------------------------------
    REQUEST_TIMEOUT_SECONDS: int = 10


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


settings = Settings(
    ENV=os.getenv("ENV", "local"),
    LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),

    ENABLE_KAFKA=_bool(os.getenv("ENABLE_KAFKA"), True),
    KAFKA_BOOTSTRAP_SERVERS=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
    KAFKA_TOPIC=os.getenv("KAFKA_TOPIC", "inbound.messages"),
    DLQ_TOPIC=os.getenv("DLQ_TOPIC", "inbound.messages.dlq"),

    ENABLE_RABBITMQ=_bool(os.getenv("ENABLE_RABBITMQ"), False),
    RABBITMQ_URL=os.getenv("RABBITMQ_URL"),
    RABBITMQ_EXCHANGE=os.getenv("RABBITMQ_EXCHANGE"),
    RABBITMQ_ROUTING_KEY=os.getenv("RABBITMQ_ROUTING_KEY"),
    RABBITMQ_QUEUE=os.getenv("RABBITMQ_QUEUE"),
    RABBITMQ_OUTBOUND_EXCHANGE=os.getenv("RABBITMQ_OUTBOUND_EXCHANGE"),
    RABBITMQ_OUTBOUND_ROUTING_KEY=os.getenv("RABBITMQ_OUTBOUND_ROUTING_KEY"),
    RABBITMQ_OUTBOUND_QUEUE=os.getenv("RABBITMQ_OUTBOUND_QUEUE"),

    DATABASE_URL=os.getenv("DATABASE_URL"),
    DATABASE_URL_ASYNC=os.getenv("DATABASE_URL_ASYNC"),

    LANGFLOW_BASE_URL=os.getenv("LANGFLOW_BASE_URL", "http://langflow:7860"),

    CALLBACK_HMAC_SECRET=os.getenv("CALLBACK_HMAC_SECRET", "dev-secret-change-me"),
    CALLBACK_MAX_RETRIES=int(os.getenv("CALLBACK_MAX_RETRIES", "3")),
    CALLBACK_BACKOFF_SECONDS=int(os.getenv("CALLBACK_BACKOFF_SECONDS", "2")),

    GATEWAY_INTERNAL_URL=os.getenv("GATEWAY_INTERNAL_URL", "http://api:8000"),

    OTEL_ENABLED=_bool(os.getenv("OTEL_ENABLED"), False),
    OTEL_EXPORTER_OTLP_ENDPOINT=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    OTEL_SERVICE_NAME=os.getenv("OTEL_SERVICE_NAME", "fd-service"),

    REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
)