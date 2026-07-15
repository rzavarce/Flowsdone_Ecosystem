import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging

from app.adapters.inbound.http.websocket import router as ws_router
from app.adapters.inbound.http.webhooks import router as webhooks_router
from app.adapters.inbound.http.internal_outbound import router as internal_router

from app.adapters.outbound.queue.kafka_publisher import KafkaPublisher
from app.adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher
from app.adapters.outbound.queue.factory import PublisherFactory

from app.application.services.ws_registry import WSRegistry
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.application.use_cases.ingest_message import IngestMessageUseCase

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("bootstrap")


# ---------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "application.startup.begin",
        extra={
            "env": settings.ENV,
            "enable_kafka": settings.ENABLE_KAFKA,
            "enable_rabbitmq": settings.ENABLE_RABBITMQ,
        },
    )

    # --------------------------------------------------------------
    # WebSocket registry + outbound handler
    # --------------------------------------------------------------
    ws_registry = WSRegistry()
    outbound_handler = HandleOutboundResponseUseCase(
        ws_registry=ws_registry
    )

    app.state.ws_registry = ws_registry
    app.state.outbound_handler = outbound_handler

    logger.info("ws.registry.initialized")

    # --------------------------------------------------------------
    # Publishers (outbound adapters)
    # --------------------------------------------------------------
    publishers: dict[str, object] = {}

    # ---------------- Kafka ----------------
    if settings.ENABLE_KAFKA:
        if not settings.KAFKA_BOOTSTRAP_SERVERS or not settings.KAFKA_TOPIC:
            raise RuntimeError(
                "ENABLE_KAFKA=true but KAFKA_BOOTSTRAP_SERVERS or KAFKA_TOPIC is missing"
            )

        logger.info(
            "kafka.publisher.initializing",
            extra={
                "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "topic": settings.KAFKA_TOPIC,
            },
        )

        kafka_publisher = KafkaPublisher(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            topic=settings.KAFKA_TOPIC,
        )
        await kafka_publisher.start()

        app.state.kafka_publisher = kafka_publisher
        publishers["kafka"] = kafka_publisher

        logger.info("kafka.publisher.ready")

    # ---------------- RabbitMQ ----------------
    if settings.ENABLE_RABBITMQ:
        if (
            not settings.RABBITMQ_URL
            or not settings.RABBITMQ_EXCHANGE
            or not settings.RABBITMQ_ROUTING_KEY
        ):
            raise RuntimeError(
                "ENABLE_RABBITMQ=true but RABBITMQ_URL / RABBITMQ_EXCHANGE / "
                "RABBITMQ_ROUTING_KEY is missing"
            )

        logger.info(
            "rabbitmq.publisher.initializing",
            extra={
                "url": settings.RABBITMQ_URL,
                "exchange": settings.RABBITMQ_EXCHANGE,
                "routing_key": settings.RABBITMQ_ROUTING_KEY,
            },
        )

        rabbitmq_publisher = RabbitMQPublisher(
            url=settings.RABBITMQ_URL,
            exchange_name=settings.RABBITMQ_EXCHANGE,
            routing_key=settings.RABBITMQ_ROUTING_KEY,
        )
        await rabbitmq_publisher.start()

        app.state.rabbitmq_publisher = rabbitmq_publisher
        publishers["rabbitmq"] = rabbitmq_publisher

        logger.info("rabbitmq.publisher.ready")

    # --------------------------------------------------------------
    # Publisher Factory
    # --------------------------------------------------------------
    publisher_factory = PublisherFactory(publishers=publishers)
    app.state.publisher_factory = publisher_factory

    logger.info(
        "publisher.factory.ready",
        extra={"transports": list(publishers.keys())},
    )

    # --------------------------------------------------------------
    # Ingest use case (usado por WebSocket y webhooks)
    # --------------------------------------------------------------
    ingest_use_case = IngestMessageUseCase(
        publisher_factory=publisher_factory,
    )
    app.state.ingest_message_use_case = ingest_use_case

    logger.info("ingest.use_case.initialized")

    logger.info("application.startup.complete")

    # --------------------------------------------------------------
    # Run application
    # --------------------------------------------------------------
    yield

    # --------------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------------
    logger.info("application.shutdown.begin")

    if settings.ENABLE_KAFKA:
        kafka_pub = getattr(app.state, "kafka_publisher", None)
        if kafka_pub:
            await kafka_pub.stop()
            logger.info("kafka.publisher.stopped")

    if settings.ENABLE_RABBITMQ:
        rabbit_pub = getattr(app.state, "rabbitmq_publisher", None)
        if rabbit_pub:
            await rabbit_pub.stop()
            logger.info("rabbitmq.publisher.stopped")

    logger.info("application.shutdown.complete")


# ---------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------

app = FastAPI(
    title="Omni API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (webchat, widgets, etc.)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(ws_router)
app.include_router(webhooks_router)
app.include_router(internal_router)