"""FastAPI application entry point: wires adapters, use cases, and routers
together at startup and exposes the resulting `app`.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from .adapters.inbound.http.admin import router as admin_router
from .adapters.inbound.http.channels import router as channels_router
from .adapters.inbound.http.internal_outbound import router as internal_router
from .adapters.inbound.http.webhooks import router as webhooks_router
from .adapters.inbound.http.websocket import router as ws_router
from .adapters.outbound.channels.factory import ChannelSenderFactory
from .adapters.outbound.db.agent_repository import SqlAlchemyAgentRepository
from .adapters.outbound.db.channel_app_repository import SqlAlchemyChannelAppRepository
from .adapters.outbound.db.channel_connection_repository import SqlAlchemyChannelConnectionRepository
from .adapters.outbound.db.project_repository import SqlAlchemyProjectRepository
from .adapters.outbound.db.tenant_repository import SqlAlchemyTenantRepository
from .adapters.outbound.db.workflow_config_repository import SqlAlchemyWorkflowConfigRepository
from .adapters.outbound.queue.factory import PublisherFactory
from .adapters.outbound.queue.kafka_publisher import KafkaPublisher
from .adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher
from .application.services.ws_registry import WSRegistry
from .application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from .application.use_cases.ingest_message import IngestMessageUseCase
from .application.use_cases.route_channel_message import RouteChannelMessageUseCase
from .core.config import settings
from .core.logging import setup_logging
from .infrastructure.database import create_engine, create_sessionmaker
from .infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("bootstrap")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build and tear down all application state around the app's lifetime.

    Constructs, in order: the WebSocket registry, the message
    publishers (Kafka/RabbitMQ) and their factory, the ingest use case,
    the database engine and admin repositories, the outbound handler
    (WebSocket + native channel senders), and the channel message
    router - then yields control to FastAPI. On shutdown, stops the
    publishers and disposes the database engine.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    logger.info(
        "application.startup.begin",
        extra={
            "env": settings.ENV,
            "enable_kafka": settings.ENABLE_KAFKA,
            "enable_rabbitmq": settings.ENABLE_RABBITMQ,
        },
    )

    # WebSocket registry
    ws_registry = WSRegistry()
    app.state.ws_registry = ws_registry

    logger.info("ws.registry.initialized")

    # Publishers (outbound adapters)
    publishers: dict[str, object] = {}

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

        await ensure_topics_exist()

        kafka_publisher = KafkaPublisher(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            topic=settings.KAFKA_TOPIC,
        )
        await kafka_publisher.start()

        app.state.kafka_publisher = kafka_publisher
        publishers["kafka"] = kafka_publisher

        logger.info("kafka.publisher.ready")

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

    publisher_factory = PublisherFactory(publishers=publishers)
    app.state.publisher_factory = publisher_factory

    logger.info(
        "publisher.factory.ready",
        extra={"transports": list(publishers.keys())},
    )

    # Ingest use case (used by WebSocket and webhooks)
    ingest_use_case = IngestMessageUseCase(
        publisher_factory=publisher_factory,
    )
    app.state.ingest_message_use_case = ingest_use_case

    logger.info("ingest.use_case.initialized")

    # Database (multi-tenant: tenants/projects/agents/workflows/channels)
    db_engine = create_engine()
    db_sessionmaker = create_sessionmaker(db_engine)
    app.state.db_engine = db_engine

    app.state.tenant_repo = SqlAlchemyTenantRepository(db_sessionmaker)
    app.state.project_repo = SqlAlchemyProjectRepository(db_sessionmaker)
    app.state.agent_repo = SqlAlchemyAgentRepository(db_sessionmaker)
    app.state.workflow_config_repo = SqlAlchemyWorkflowConfigRepository(db_sessionmaker)
    app.state.channel_connection_repo = SqlAlchemyChannelConnectionRepository(db_sessionmaker)
    app.state.channel_app_repo = SqlAlchemyChannelAppRepository(db_sessionmaker)

    logger.info("database.repositories.ready")

    # Outbound handler (WebSocket + native channel senders). Built
    # after the database repositories so it can be given a real
    # channel_connection_repo.
    outbound_handler = HandleOutboundResponseUseCase(
        ws_registry=ws_registry,
        channel_connection_repo=app.state.channel_connection_repo,
        channel_senders=ChannelSenderFactory().build_all(),
    )
    app.state.outbound_handler = outbound_handler

    logger.info("outbound.handler.initialized")

    # Channel message routing (native webhooks -> Kafka -> Langflow)
    app.state.route_channel_message_use_case = RouteChannelMessageUseCase(
        channel_connection_repo=app.state.channel_connection_repo,
        ingest_message_use_case=ingest_use_case,
    )

    logger.info("route_channel_message.use_case.initialized")

    logger.info("application.startup.complete")

    yield

    # Shutdown
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

    db_engine = getattr(app.state, "db_engine", None)
    if db_engine:
        await db_engine.dispose()
        logger.info("database.engine.disposed")

    logger.info("application.shutdown.complete")


app = FastAPI(
    title="Omni API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that always disables caching, so webchat widget
    updates are visible immediately without a hard refresh.
    """

    async def get_response(self, path: str, scope):
        """Serve a static file with cache-disabling headers.

        Args:
            path (str): Path of the requested static file.
            scope: ASGI connection scope.

        Returns:
            Response: The response, with Cache-Control/Pragma/Expires
            headers set to disable caching.
        """
        response = await super().get_response(path, scope)
        if isinstance(response, Response):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


@app.middleware("http")
async def no_cache_static(request, call_next):
    """Disable caching on any response served under /static/.

    Args:
        request: The incoming request.
        call_next: The next handler in the middleware chain.

    Returns:
        Response: The response, with caching disabled if the path is
        under /static/.
    """
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Static files (webchat, widgets, etc.)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", NoCacheStaticFiles(directory=static_dir, html=True), name="static")

# Routers
app.include_router(ws_router)
app.include_router(webhooks_router)
app.include_router(internal_router)
app.include_router(channels_router)
app.include_router(admin_router)
