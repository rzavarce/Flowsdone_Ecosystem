"""Application settings, loaded from environment variables at import time."""

import os
from typing import Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """All configuration for the gateway and its workers.

    Values are populated once at import time from environment
    variables (see the `settings = Settings(...)` call below); the
    field defaults here only apply when constructing a Settings
    instance directly (e.g. in tests).
    """

    # Environment
    ENV: str = "local"
    LOG_LEVEL: str = "INFO"

    # Kafka
    ENABLE_KAFKA: bool = True
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC: str = "inbound.messages"
    # Partitions for KAFKA_TOPIC/DLQ_TOPIC. Messages are partitioned by
    # channel (key=channel), so this is the ceiling on how many
    # channels can be isolated from each other by scaling
    # kafka_inbound_worker replicas later (docker compose up -d
    # --scale kafka_inbound_worker=N), without touching code.
    KAFKA_TOPIC_PARTITIONS: int = 6
    DLQ_TOPIC: str = "inbound.messages.dlq"
    # Dedicated topic for the voice channel, kept separate from
    # KAFKA_TOPIC so a burst of calls never delays/competes with text
    # channels for kafka_inbound_worker capacity.
    VOICE_KAFKA_TOPIC: str = "voice.messages"
    VOICE_KAFKA_TOPIC_PARTITIONS: int = 3

    # Redis (voice call session state, see CallSessionRepositoryPort)
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    # Upper bound on call duration; the session is looked up once when
    # the streaming WebSocket connects, shortly after this is written.
    CALL_SESSION_TTL_SECONDS: int = 7200

    # RabbitMQ
    ENABLE_RABBITMQ: bool = False
    RABBITMQ_URL: Optional[str] = None
    RABBITMQ_EXCHANGE: Optional[str] = None
    RABBITMQ_ROUTING_KEY: Optional[str] = None
    RABBITMQ_QUEUE: Optional[str] = None

    RABBITMQ_OUTBOUND_EXCHANGE: Optional[str] = None
    RABBITMQ_OUTBOUND_ROUTING_KEY: Optional[str] = None
    RABBITMQ_OUTBOUND_QUEUE: Optional[str] = None

    # Database (no hard crash if unset; only raised when actually used)
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_ASYNC: Optional[str] = None
    DATABASE_URL_SQLALCHEMY: Optional[str] = None

    # Langflow
    LANGFLOW_BASE_URL: str = "http://langflow:7860"
    LANGFLOW_API_KEY: Optional[str] = None

    # Multi-tenant SaaS: admin API + credentials encryption
    ADMIN_API_KEY: str = "dev-admin-key-change-me"
    CHANNEL_CREDENTIALS_ENCRYPTION_KEY: Optional[str] = None

    # Channels (inbound webhooks)
    # Meta/X/TikTok app secrets (shared across the whole SaaS) and the
    # per-bot Telegram secret_token no longer live here - they are
    # managed via /internal/admin/channel-apps and
    # channel_connections.credentials respectively (see README section
    # 9). EVOLUTION_API_KEY remains the shared secret of our own
    # Evolution API instance.
    EVOLUTION_API_KEY: Optional[str] = None

    # Channels (outbound message sending)
    EVOLUTION_API_BASE_URL: str = "http://evolution:8080"
    META_GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
    META_GRAPH_API_VERSION: str = "v21.0"
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org"
    # Twitter/TikTok: real sending is not implemented yet (see the
    # channel_sender for those channels) - these settings only exist
    # for when it is activated; they are unused for now.
    TWITTER_API_BASE_URL: Optional[str] = None
    TIKTOK_API_BASE_URL: Optional[str] = None

    # Webhook callbacks
    CALLBACK_HMAC_SECRET: str = "dev-secret-change-me"
    CALLBACK_MAX_RETRIES: int = 3
    CALLBACK_BACKOFF_SECONDS: int = 2
    GATEWAY_INTERNAL_URL: str = "http://api:8000"
    # Public, internet-reachable base URL of this gateway (unlike
    # GATEWAY_INTERNAL_URL, which is only reachable inside the Docker
    # network). Used to build callback URLs that external platforms
    # must call back into, e.g. Telegram's setWebhook (see
    # TelegramWebhookRegistrar).
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # OpenTelemetry (logs + traces)
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = "fd-service"

    # Voice demo softphone (dev/testing only, see .env). Optional: the
    # /voice-demo/token endpoint 404s if unset, rather than failing
    # gateway startup - unlike the production voice channel, this is
    # not required for the app to run.
    VOICE_DEMO_TWILIO_ACCOUNT_SID: Optional[str] = None
    VOICE_DEMO_TWILIO_API_KEY_SID: Optional[str] = None
    VOICE_DEMO_TWILIO_API_KEY_SECRET: Optional[str] = None
    VOICE_DEMO_TWILIO_TWIML_APP_SID: Optional[str] = None

    # Misc
    REQUEST_TIMEOUT_SECONDS: int = 10


def _bool(value: Optional[str], default: bool) -> bool:
    """Parse an environment variable string as a boolean.

    Args:
        value (Optional[str]): The raw environment variable value, or
            None if unset.
        default (bool): Value to return if `value` is None.

    Returns:
        bool: True if `value` is one of "1", "true", "yes", "on"
        (case-insensitive); False otherwise; `default` if `value` is None.
    """
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
    VOICE_KAFKA_TOPIC=os.getenv("VOICE_KAFKA_TOPIC", "voice.messages"),
    VOICE_KAFKA_TOPIC_PARTITIONS=int(os.getenv("VOICE_KAFKA_TOPIC_PARTITIONS", "3")),

    REDIS_HOST=os.getenv("REDIS_HOST", "redis"),
    REDIS_PORT=int(os.getenv("REDIS_PORT", "6379")),
    REDIS_PASSWORD=os.getenv("REDIS_PASSWORD"),
    CALL_SESSION_TTL_SECONDS=int(os.getenv("CALL_SESSION_TTL_SECONDS", "7200")),

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
    PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"),

    OTEL_ENABLED=_bool(os.getenv("OTEL_ENABLED"), False),
    OTEL_EXPORTER_OTLP_ENDPOINT=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    OTEL_SERVICE_NAME=os.getenv("OTEL_SERVICE_NAME", "fd-service"),

    VOICE_DEMO_TWILIO_ACCOUNT_SID=os.getenv("VOICE_DEMO_TWILIO_ACCOUNT_SID"),
    VOICE_DEMO_TWILIO_API_KEY_SID=os.getenv("VOICE_DEMO_TWILIO_API_KEY_SID"),
    VOICE_DEMO_TWILIO_API_KEY_SECRET=os.getenv("VOICE_DEMO_TWILIO_API_KEY_SECRET"),
    VOICE_DEMO_TWILIO_TWIML_APP_SID=os.getenv("VOICE_DEMO_TWILIO_TWIML_APP_SID"),

    REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
)
