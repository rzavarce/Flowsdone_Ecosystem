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
    # Particiones de KAFKA_TOPIC/DLQ_TOPIC. Los mensajes se particionan por
    # canal (key=channel), así que esto es el techo de canales que pueden
    # aislarse entre sí escalando réplicas de kafka_inbound_worker más
    # adelante (docker compose up -d --scale kafka_inbound_worker=N), sin
    # tocar código.
    KAFKA_TOPIC_PARTITIONS: int = 6
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
    DATABASE_URL_SQLALCHEMY: Optional[str] = None

    # --------------------------------------------------
    # Langflow
    # --------------------------------------------------
    LANGFLOW_BASE_URL: str = "http://langflow:7860"
    LANGFLOW_API_KEY: Optional[str] = None

    # --------------------------------------------------
    # Multi-tenant SaaS: admin API + cifrado de credenciales
    # --------------------------------------------------
    ADMIN_API_KEY: str = "dev-admin-key-change-me"
    CHANNEL_CREDENTIALS_ENCRYPTION_KEY: Optional[str] = None

    # --------------------------------------------------
    # Canales (webhooks entrantes)
    # --------------------------------------------------
    # Los secrets de App de Meta/X/TikTok (compartidos por todo el SaaS) y el
    # secret_token por bot de Telegram ya NO viven acá — se gestionan por
    # /internal/admin/channel-apps y channel_connections.credentials
    # respectivamente (ver README sección 9). EVOLUTION_API_KEY sigue siendo
    # el shared secret de nuestra propia instancia de Evolution API.
    EVOLUTION_API_KEY: Optional[str] = None

    # --------------------------------------------------
    # Canales (envío de mensajes salientes)
    # --------------------------------------------------
    EVOLUTION_API_BASE_URL: str = "http://evolution:8080"
    META_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
    META_GRAPH_API_VERSION: str = "v21.0"
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"
    # Twitter/TikTok: el envío real todavía no está implementado (ver
    # channel_sender de esos canales) — estos settings solo existen para
    # cuando se active, no se usan todavía.
    TWITTER_API_BASE_URL: Optional[str] = None
    TIKTOK_API_BASE_URL: Optional[str] = None

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
    KAFKA_TOPIC_PARTITIONS=int(os.getenv("KAFKA_TOPIC_PARTITIONS", "6")),
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
    DATABASE_URL_SQLALCHEMY=os.getenv("DATABASE_URL_SQLALCHEMY"),

    LANGFLOW_BASE_URL=os.getenv("LANGFLOW_BASE_URL", "http://langflow:7860"),
    LANGFLOW_API_KEY=os.getenv("LANGFLOW_API_KEY"),

    ADMIN_API_KEY=os.getenv("ADMIN_API_KEY", "dev-admin-key-change-me"),
    CHANNEL_CREDENTIALS_ENCRYPTION_KEY=os.getenv("CHANNEL_CREDENTIALS_ENCRYPTION_KEY"),

    EVOLUTION_API_KEY=os.getenv("EVOLUTION_API_KEY"),

    EVOLUTION_API_BASE_URL=os.getenv("EVOLUTION_API_BASE_URL", "http://evolution:8080"),
    META_GRAPH_API_BASE_URL=os.getenv("META_GRAPH_API_BASE_URL", "https://graph.facebook.com"),
    META_GRAPH_API_VERSION=os.getenv("META_GRAPH_API_VERSION", "v21.0"),
    TELEGRAM_API_BASE_URL=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org"),
    TWITTER_API_BASE_URL=os.getenv("TWITTER_API_BASE_URL"),
    TIKTOK_API_BASE_URL=os.getenv("TIKTOK_API_BASE_URL"),

    CALLBACK_HMAC_SECRET=os.getenv("CALLBACK_HMAC_SECRET", "dev-secret-change-me"),
    CALLBACK_MAX_RETRIES=int(os.getenv("CALLBACK_MAX_RETRIES", "3")),
    CALLBACK_BACKOFF_SECONDS=int(os.getenv("CALLBACK_BACKOFF_SECONDS", "2")),

    GATEWAY_INTERNAL_URL=os.getenv("GATEWAY_INTERNAL_URL", "http://api:8000"),

    OTEL_ENABLED=_bool(os.getenv("OTEL_ENABLED"), False),
    OTEL_EXPORTER_OTLP_ENDPOINT=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    OTEL_SERVICE_NAME=os.getenv("OTEL_SERVICE_NAME", "fd-service"),

    REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
)