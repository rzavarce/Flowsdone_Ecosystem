"""FastAPI application entry point: wires adapters, use cases, and routers
together at startup and exposes the resulting `app`.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from app.adapters.inbound.http.admin import router as admin_router
from app.adapters.inbound.http.channels import router as channels_router
from app.adapters.inbound.http.internal_outbound import router as internal_router
from app.adapters.inbound.http.voice import router as voice_router
from app.adapters.inbound.http.voice_demo import router as voice_demo_router
from app.adapters.inbound.http.webhooks import router as webhooks_router
from app.adapters.inbound.http.websocket import router as ws_router
from app.adapters.outbound.apps.factory import AppConnectorFactory
from app.adapters.outbound.channels.factory import ChannelSenderFactory
from app.adapters.outbound.channels.webhook_registrar_factory import WebhookRegistrarFactory
from app.adapters.outbound.db.agent_repository import SqlAlchemyAgentRepository
from app.adapters.outbound.db.channel_app_repository import SqlAlchemyChannelAppRepository
from app.adapters.outbound.db.channel_connection_repository import SqlAlchemyChannelConnectionRepository
from app.adapters.outbound.db.project_repository import SqlAlchemyProjectRepository
from app.adapters.outbound.db.tenant_repository import SqlAlchemyTenantRepository
from app.adapters.outbound.db.workflow_config_repository import SqlAlchemyWorkflowConfigRepository
from app.adapters.outbound.queue.factory import PublisherFactory
from app.adapters.outbound.queue.kafka_publisher import KafkaPublisher
from app.adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher
from app.adapters.outbound.security.secret_generator import RandomHexSecretGenerator
from app.adapters.outbound.session.postgres_session_history_repository import (
    PostgresSessionHistoryRepository,
)
from app.adapters.outbound.session.redis_session_repository import RedisSessionRepository
from app.adapters.outbound.voice.redis_call_session_repository import RedisCallSessionRepository
from app.adapters.outbound.voice.twilio_voice_provider import TwilioVoiceProviderAdapter
from app.application.services.switchboard import Switchboard
from app.application.services.ws_registry import WSRegistry
from app.application.use_cases.create_channel_connection import CreateChannelConnectionUseCase
from app.application.use_cases.delete_channel_connection import DeleteChannelConnectionUseCase
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.application.use_cases.ingest_message import IngestMessageUseCase
from app.application.use_cases.update_channel_connection import UpdateChannelConnectionUseCase
from app.application.use_cases.upsert_channel_app import UpsertChannelAppUseCase
from app.core.config import settings
from app.core.logging import setup_logging
from app.infrastructure.database import create_engine, create_sessionmaker
from app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("bootstrap")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build and tear down all application state around the app's lifetime.

    Constructs, in order: the WebSocket registry, the voice call
    registry and its Redis-backed session store, Switchboard's fast
    (Redis) session repo, the message publishers (Kafka/RabbitMQ,
    including the voice channel's dedicated Kafka topic) and their
    factory, the ingest use case, the database engine and admin
    repositories, Switchboard's durable (Postgres) history repo, the
    outbound handler (WebSocket + native channel senders, including
    voice), and the Switchboard itself (the single entry point every
    channel now routes inbound turns through) - then yields control to
    FastAPI. On shutdown, stops the publishers, closes the Redis
    client, and disposes the database engine.

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

    # Voice call registry (separate instance/keyspace from ws_registry:
    # keyed by call_sid rather than conversation_id, so the voice
    # module never shares mutable state with webchat).
    call_session_registry = WSRegistry()
    app.state.call_session_registry = call_session_registry

    logger.info("ws.registry.initialized")

    # Voice call session storage (Redis) and provider adapter. Built
    # unconditionally - unlike Kafka/RabbitMQ, voice has no on/off
    # flag; a call simply cannot be routed if channel_apps/twilio is
    # never configured, exactly like any other channel with missing
    # credentials.
    redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
    app.state.redis_client = redis_client
    app.state.call_session_repo = RedisCallSessionRepository(redis_client)
    app.state.voice_provider = TwilioVoiceProviderAdapter()

    logger.info("voice.dependencies.initialized")

    # Switchboard's fast session state (Redis) - shares the same
    # redis_client as voice's CallSession store; separate key prefix
    # keeps the two keyspaces from colliding.
    session_repo = RedisSessionRepository(redis_client)
    app.state.session_repo = session_repo

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

        # Dedicated publisher/topic for the voice channel (see
        # VOICE_KAFKA_TOPIC), kept separate from KAFKA_TOPIC so a
        # burst of calls never competes with text channels for
        # kafka_inbound_worker capacity.
        voice_kafka_publisher = KafkaPublisher(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            topic=settings.VOICE_KAFKA_TOPIC,
        )
        await voice_kafka_publisher.start()

        app.state.voice_kafka_publisher = voice_kafka_publisher
        publishers["kafka_voice"] = voice_kafka_publisher

        logger.info("kafka.voice_publisher.ready", extra={"topic": settings.VOICE_KAFKA_TOPIC})

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

    # Switchboard's durable transcript (Postgres) - needs db_sessionmaker,
    # so it is built here rather than alongside session_repo above.
    session_history_repo = PostgresSessionHistoryRepository(db_sessionmaker)
    app.state.session_history_repo = session_history_repo

    logger.info("database.repositories.ready")

    # Channel connection create/update (auto-generate webhook secrets
    # and keep external platform registration in sync for channels
    # that support it, e.g. Telegram). Secret generator and registrars
    # are shared instances: both use cases must agree on which
    # channels are auto-registered.
    secret_generator = RandomHexSecretGenerator()
    webhook_registrars = WebhookRegistrarFactory().build_all()

    app.state.create_channel_connection_use_case = CreateChannelConnectionUseCase(
        channel_connection_repo=app.state.channel_connection_repo,
        secret_generator=secret_generator,
        webhook_registrars=webhook_registrars,
    )
    app.state.update_channel_connection_use_case = UpdateChannelConnectionUseCase(
        channel_connection_repo=app.state.channel_connection_repo,
        secret_generator=secret_generator,
        webhook_registrars=webhook_registrars,
    )
    app.state.delete_channel_connection_use_case = DeleteChannelConnectionUseCase(
        channel_connection_repo=app.state.channel_connection_repo,
        webhook_registrars=webhook_registrars,
    )

    # Same shared secret_generator: channel_apps (e.g. Meta's
    # webhook_verify_token) get the same auto-generation treatment as
    # channel_connections' per-connection secrets.
    app.state.upsert_channel_app_use_case = UpsertChannelAppUseCase(
        channel_app_repo=app.state.channel_app_repo,
        secret_generator=secret_generator,
    )

    logger.info("channel_connection.use_cases.initialized")

    # Outbound handler (WebSocket + native channel senders). Built
    # after the database repositories so it can be given a real
    # channel_connection_repo.
    outbound_handler = HandleOutboundResponseUseCase(
        ws_registry=ws_registry,
        channel_connection_repo=app.state.channel_connection_repo,
        channel_senders=ChannelSenderFactory().build_all(
            call_session_registry=call_session_registry,
            voice_provider=app.state.voice_provider,
        ),
        session_repo=session_repo,
        session_history_repo=session_history_repo,
        session_ttl_seconds=settings.SESSION_TTL_SECONDS,
    )
    app.state.outbound_handler = outbound_handler

    logger.info("outbound.handler.initialized")

    # Switchboard: single entry point for every inbound channel turn.
    # Built after outbound_handler, which it needs to deliver any
    # AppConnector result that isn't handled asynchronously.
    app.state.switchboard = Switchboard(
        channel_connection_repo=app.state.channel_connection_repo,
        session_repo=session_repo,
        session_history_repo=session_history_repo,
        app_connectors=AppConnectorFactory().build_all(ingest_message_use_case=ingest_use_case),
        outbound_handler=outbound_handler,
        session_ttl_seconds=settings.SESSION_TTL_SECONDS,
    )

    logger.info("switchboard.initialized")

    logger.info("application.startup.complete")

    yield

    # Shutdown
    logger.info("application.shutdown.begin")

    if settings.ENABLE_KAFKA:
        kafka_pub = getattr(app.state, "kafka_publisher", None)
        if kafka_pub:
            await kafka_pub.stop()
            logger.info("kafka.publisher.stopped")

        voice_kafka_pub = getattr(app.state, "voice_kafka_publisher", None)
        if voice_kafka_pub:
            await voice_kafka_pub.stop()
            logger.info("kafka.voice_publisher.stopped")

    redis_client = getattr(app.state, "redis_client", None)
    if redis_client:
        await redis_client.aclose()
        logger.info("redis.client.closed")

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
app.include_router(voice_router)
app.include_router(voice_demo_router)
app.include_router(admin_router)
