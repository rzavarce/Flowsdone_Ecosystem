"""FastAPI application entry point: wires adapters, use cases, and routers
together at startup and exposes the resulting `app`.
"""

import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from app.adapters.inbound.http.admin import router as admin_router
from app.adapters.inbound.http.auth import router as auth_router
from app.adapters.inbound.http.me import router as me_router
from app.adapters.inbound.http.errors import register_error_handlers
from app.adapters.inbound.http.channels import router as channels_router
from app.adapters.inbound.http.contact import router as contact_router
from app.adapters.inbound.http.langflow_sso import router as langflow_sso_router
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
from app.adapters.outbound.db.langflow_account_repository import SqlAlchemyLangflowAccountRepository
from app.adapters.outbound.db.project_repository import SqlAlchemyProjectRepository
from app.adapters.outbound.db.tenant_billing_profile_repository import (
    SqlAlchemyTenantBillingProfileRepository,
)
from app.adapters.outbound.db.tenant_repository import SqlAlchemyTenantRepository
from app.adapters.outbound.db.user_repository import SqlAlchemyUserAvatarRepository, SqlAlchemyUserRepository
from app.adapters.outbound.email.resend_client import ResendEmailAdapter
from app.adapters.outbound.session.redis_account_token_store import RedisAccountTokenStore
from app.adapters.outbound.session.redis_auth_session_repository import RedisAuthSessionRepository
from app.adapters.outbound.session.redis_login_throttle import RedisLoginThrottle
from app.adapters.outbound.session.redis_sso_ticket_store import RedisSsoTicketStore
from app.adapters.outbound.db.workflow_config_repository import SqlAlchemyWorkflowConfigRepository
from app.adapters.outbound.billing.redis_quota_counter import RedisQuotaCounter
from app.adapters.outbound.clickhouse.http_client import ClickHouseHttpClient
from app.adapters.outbound.clickhouse.message_archive import ClickHouseMessageArchive
from app.adapters.outbound.clickhouse.usage_store import ClickHouseUsageStore
from app.adapters.outbound.conversations.event_publishers import (
    BrokerConversationEventPublisher,
    NullConversationEventPublisher,
)
from app.adapters.outbound.db.billing_repositories import (
    SqlAlchemyPlanRepository,
    SqlAlchemyStatementRepository,
    SqlAlchemySubscriptionRepository,
)
from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.adapters.outbound.db.usage_repositories import SqlAlchemyCostRateRepository
from app.adapters.outbound.langflow.admin_client import LangflowAdminClient
from app.adapters.outbound.queue.factory import PublisherFactory
from app.adapters.outbound.queue.kafka_publisher import KafkaPublisher
from app.adapters.outbound.queue.rabbitmq_publisher import RabbitMQPublisher
from app.adapters.outbound.security.scrypt_password_hasher import ScryptPasswordHasher
from app.adapters.outbound.security.secret_generator import RandomHexSecretGenerator
from app.adapters.outbound.session.postgres_session_history_repository import (
    PostgresSessionHistoryRepository,
)
from app.adapters.outbound.session.redis_session_repository import RedisSessionRepository
from app.adapters.outbound.voice.redis_call_session_repository import RedisCallSessionRepository
from app.adapters.outbound.voice.twilio_voice_provider import TwilioVoiceProviderAdapter
from app.application.services.conversation_tracker import ConversationTracker
from app.application.services.quota_alerts import QuotaAlertMailer
from app.application.services.quota_gate import QuotaGate
from app.application.use_cases.billing import (
    CloseBillingPeriodUseCase,
    ComputeStatementUseCase,
    ListUnratedMetersUseCase,
    PlanPricingInsightUseCase,
)
from app.application.use_cases.conversation_queries import GetConversationDetailUseCase
from app.application.services.switchboard import Switchboard
from app.application.services.ws_registry import WSRegistry
from app.application.services.access_control import AccessControl
from app.application.use_cases.activate_account import ActivateAccountUseCase
from app.application.use_cases.authenticate_user import AuthenticateUserUseCase
from app.application.use_cases.create_tenant import CreateTenantUseCase
from app.application.use_cases.create_user import CreateUserUseCase
from app.application.use_cases.create_channel_connection import CreateChannelConnectionUseCase
from app.application.use_cases.delete_channel_connection import DeleteChannelConnectionUseCase
from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.application.use_cases.ingest_message import IngestMessageUseCase
from app.application.use_cases.langflow_sso import PrepareLangflowSessionUseCase, RedeemLangflowTicketUseCase
from app.application.use_cases.delete_project import DeleteProjectUseCase
from app.application.use_cases.delete_tenant import DeleteTenantUseCase
from app.application.use_cases.manage_agents import ListProjectFlowsUseCase, ManageAgentsUseCase
from app.application.use_cases.onboarding import CreateBaseAgentUseCase, GetOnboardingStatusUseCase
from app.application.use_cases.logout_user import LogoutUserUseCase
from app.application.use_cases.manage_profile import (
    RemoveAvatarUseCase,
    SetAvatarUseCase,
    UpdateOwnProfileUseCase,
)
from app.application.use_cases.manage_users import DeleteUserUseCase, UpdateUserUseCase
from app.application.use_cases.provision_user import ProvisionUserUseCase
from app.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from app.application.use_cases.reset_password import ResetPasswordUseCase
from app.application.use_cases.send_contact_request import SendContactRequestUseCase
from app.application.use_cases.update_channel_connection import UpdateChannelConnectionUseCase
from app.application.use_cases.upsert_channel_app import UpsertChannelAppUseCase
from app.core.config import settings
from app.domain.models.conversation import ConversationLifecyclePolicy
from app.core.logging import setup_logging
from app.core.tracing import instrument_fastapi_app, setup_tracing
from app.infrastructure.database import create_engine, create_sessionmaker
from app.infrastructure.kafka_admin import ensure_topics_exist

setup_logging(settings.LOG_LEVEL)
setup_tracing()
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
    app.state.tenant_billing_profile_repo = SqlAlchemyTenantBillingProfileRepository(db_sessionmaker)
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

    # Conversations: live records in Postgres, every message published
    # to CONVERSATION_EVENTS_TOPIC for the conversations worker to
    # archive into ClickHouse. Without Kafka, conversations are still
    # tracked but messages are not archived.
    if settings.ENABLE_KAFKA:
        conversation_events_kafka = KafkaPublisher(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            topic=settings.CONVERSATION_EVENTS_TOPIC,
        )
        await conversation_events_kafka.start()
        app.state.conversation_events_kafka_publisher = conversation_events_kafka
        conversation_event_publisher = BrokerConversationEventPublisher(conversation_events_kafka)
    else:
        conversation_event_publisher = NullConversationEventPublisher()

    conversation_repo = SqlAlchemyConversationRepository(db_sessionmaker)
    app.state.conversation_repo = conversation_repo
    conversation_tracker = ConversationTracker(
        conversation_repo=conversation_repo,
        event_publisher=conversation_event_publisher,
        session_history_repo=session_history_repo,
        policy=ConversationLifecyclePolicy(
            inactivity=timedelta(seconds=settings.CONVERSATION_INACTIVITY_SECONDS),
            max_duration=timedelta(seconds=settings.CONVERSATION_MAX_DURATION_SECONDS),
        ),
    )
    app.state.conversation_tracker = conversation_tracker
    logger.info("conversations.tracker.ready")

    # Console (PWA) authentication: users in Postgres, opaque sessions and
    # login throttling in Redis (same client as voice/switchboard; own key
    # prefixes), scrypt for passwords.
    user_repo = SqlAlchemyUserRepository(db_sessionmaker)
    auth_sessions = RedisAuthSessionRepository(redis_client)
    password_hasher = ScryptPasswordHasher()
    # Shared with /auth/forgot-password and the IP throttle on
    # /auth/activate|reset-password (see auth.py) - same counters, own key
    # prefixes per caller, so exposed on app.state instead of being private
    # to the login use case.
    login_throttle = RedisLoginThrottle(redis_client)
    app.state.login_throttle = login_throttle
    app.state.user_repo = user_repo
    app.state.authenticate_user_use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        tenant_repo=app.state.tenant_repo,
        hasher=password_hasher,
        sessions=auth_sessions,
        throttle=login_throttle,
        session_ttl_seconds=settings.AUTH_SESSION_TTL_SECONDS,
        window_seconds=settings.AUTH_LOGIN_WINDOW_SECONDS,
        max_failures_per_email=settings.AUTH_LOGIN_MAX_FAILURES_PER_EMAIL,
        max_failures_per_ip=settings.AUTH_LOGIN_MAX_FAILURES_PER_IP,
    )
    app.state.get_current_user_use_case = GetCurrentUserUseCase(
        sessions=auth_sessions,
        user_repo=user_repo,
        tenant_repo=app.state.tenant_repo,
        session_ttl_seconds=settings.AUTH_SESSION_TTL_SECONDS,
    )
    app.state.logout_user_use_case = LogoutUserUseCase(sessions=auth_sessions)

    # Admin API authorization (role matrix + tenant scoping) and user management.
    app.state.access_control = AccessControl(
        project_repo=app.state.project_repo, agent_repo=app.state.agent_repo
    )
    app.state.create_user_use_case = CreateUserUseCase(
        user_repo=user_repo, tenant_repo=app.state.tenant_repo, hasher=password_hasher
    )
    app.state.update_user_use_case = UpdateUserUseCase(
        user_repo=user_repo,
        tenant_repo=app.state.tenant_repo,
        hasher=password_hasher,
        sessions=auth_sessions,
    )
    app.state.delete_user_use_case = DeleteUserUseCase(user_repo=user_repo, sessions=auth_sessions)
    # Self-service profile ("My profile" in the PWA) and profile photos,
    # shared by /me/* and the admin Users endpoints.
    user_avatar_repo = SqlAlchemyUserAvatarRepository(db_sessionmaker)
    app.state.user_avatar_repo = user_avatar_repo
    app.state.update_own_profile_use_case = UpdateOwnProfileUseCase(
        user_repo=user_repo, tenant_repo=app.state.tenant_repo
    )
    app.state.set_avatar_use_case = SetAvatarUseCase(avatar_repo=user_avatar_repo)
    app.state.remove_avatar_use_case = RemoveAvatarUseCase(avatar_repo=user_avatar_repo)
    logger.info("auth.dependencies.initialized")

    # Account activation by email (see application/use_cases/provision_user.py)
    # and "forgot my password" - Resend (HTTPS API, not SMTP: the VPS has
    # outbound SMTP blocked) plus two single-use Redis token stores that can
    # never be redeemed as one another (different key prefixes).
    email_sender = ResendEmailAdapter()
    app.state.email_sender = email_sender
    app.state.send_contact_request_use_case = SendContactRequestUseCase(
        email_sender=email_sender,
        # Own instance of the Redis counters; keys are prefixed "contact:".
        throttle=RedisLoginThrottle(redis_client),
        recipient=settings.CONTACT_EMAIL_TO,
        max_per_ip=settings.CONTACT_MAX_PER_IP,
        window_seconds=settings.CONTACT_WINDOW_SECONDS,
    )
    activation_tokens = RedisAccountTokenStore(redis_client, prefix="auth:activate:")
    reset_tokens = RedisAccountTokenStore(redis_client, prefix="auth:reset:")
    app.state.provision_user_use_case = ProvisionUserUseCase(
        create_user=app.state.create_user_use_case,
        user_repo=user_repo,
        tokens=activation_tokens,
        mailer=email_sender,
        ttl_seconds=settings.ACCOUNT_ACTIVATION_TTL_SECONDS,
        activation_base_url=settings.PWA_PUBLIC_URL,
    )
    app.state.activate_account_use_case = ActivateAccountUseCase(
        tokens=activation_tokens,
        user_repo=user_repo,
        tenant_repo=app.state.tenant_repo,
        hasher=password_hasher,
        sessions=auth_sessions,
        session_ttl_seconds=settings.AUTH_SESSION_TTL_SECONDS,
    )
    app.state.request_password_reset_use_case = RequestPasswordResetUseCase(
        user_repo=user_repo,
        tokens=reset_tokens,
        mailer=email_sender,
        throttle=login_throttle,
        ttl_seconds=settings.PASSWORD_RESET_TTL_SECONDS,
        reset_base_url=settings.PWA_PUBLIC_URL,
        window_seconds=settings.AUTH_LOGIN_WINDOW_SECONDS,
        max_requests_per_email=settings.AUTH_LOGIN_MAX_FAILURES_PER_EMAIL,
        max_requests_per_ip=settings.AUTH_LOGIN_MAX_FAILURES_PER_IP,
    )
    app.state.reset_password_use_case = ResetPasswordUseCase(
        tokens=reset_tokens,
        user_repo=user_repo,
        tenant_repo=app.state.tenant_repo,
        hasher=password_hasher,
        sessions=auth_sessions,
        session_ttl_seconds=settings.AUTH_SESSION_TTL_SECONDS,
    )
    app.state.create_tenant_use_case = CreateTenantUseCase(
        tenant_repo=app.state.tenant_repo,
        user_repo=user_repo,
        provision_user=app.state.provision_user_use_case,
    )
    logger.info("account_activation.dependencies.initialized")

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

    # Embedded Langflow SSO: one Langflow user per tenant, one folder per
    # project, and single-use tickets (Redis) to hand the browser over.
    langflow_accounts = SqlAlchemyLangflowAccountRepository(db_sessionmaker)
    langflow_admin = LangflowAdminClient()
    langflow_tickets = RedisSsoTicketStore(redis_client)
    app.state.langflow_admin_client = langflow_admin
    app.state.prepare_langflow_session_use_case = PrepareLangflowSessionUseCase(
        tenant_repo=app.state.tenant_repo,
        project_repo=app.state.project_repo,
        accounts=langflow_accounts,
        langflow=langflow_admin,
        secret_generator=secret_generator,
        tickets=langflow_tickets,
        ticket_ttl_seconds=settings.LANGFLOW_SSO_TICKET_TTL_SECONDS,
    )
    # Agents: register the flows of a project's Langflow folder (reuses the
    # SSO use case to open the tenant's Langflow as its own user).
    app.state.list_project_flows_use_case = ListProjectFlowsUseCase(
        project_repo=app.state.project_repo,
        agent_repo=app.state.agent_repo,
        workspace=app.state.prepare_langflow_session_use_case,
        langflow=langflow_admin,
    )
    app.state.delete_tenant_use_case = DeleteTenantUseCase(
        tenant_repo=app.state.tenant_repo,
        user_repo=user_repo,
        delete_user=app.state.delete_user_use_case,
        accounts=langflow_accounts,
        langflow=langflow_admin,
    )
    app.state.delete_project_use_case = DeleteProjectUseCase(
        project_repo=app.state.project_repo,
        accounts=langflow_accounts,
        workspace=app.state.prepare_langflow_session_use_case,
        langflow=langflow_admin,
    )
    app.state.manage_agents_use_case = ManageAgentsUseCase(
        agent_repo=app.state.agent_repo,
        channel_connection_repo=app.state.channel_connection_repo,
        flows=app.state.list_project_flows_use_case,
    )
    app.state.create_base_agent_use_case = CreateBaseAgentUseCase(
        project_repo=app.state.project_repo,
        tenant_repo=app.state.tenant_repo,
        workspace=app.state.prepare_langflow_session_use_case,
        langflow=langflow_admin,
        manage_agents=app.state.manage_agents_use_case,
    )
    app.state.redeem_langflow_ticket_use_case = RedeemLangflowTicketUseCase(
        accounts=langflow_accounts, langflow=langflow_admin, tickets=langflow_tickets
    )

    # Conversation archive and usage (ClickHouse), plans/subscriptions/
    # statements (Postgres) and the quota gate (Redis counters) - see
    # README section 24. Built after email_sender (quota alerts) and before
    # Switchboard (which checks every inbound message against the quota).
    clickhouse = ClickHouseHttpClient(
        base_url=settings.CLICKHOUSE_URL,
        database=settings.CLICKHOUSE_DATABASE,
        user=settings.CLICKHOUSE_APP_USER,
        password=settings.CLICKHOUSE_APP_PASSWORD,
    )
    app.state.clickhouse = clickhouse
    usage_store = ClickHouseUsageStore(clickhouse)
    app.state.cost_rate_repo = SqlAlchemyCostRateRepository(db_sessionmaker)
    app.state.plan_repo = SqlAlchemyPlanRepository(db_sessionmaker)
    app.state.subscription_repo = SqlAlchemySubscriptionRepository(db_sessionmaker)
    app.state.statement_repo = SqlAlchemyStatementRepository(db_sessionmaker)
    quota_gate = QuotaGate(
        subscriptions=app.state.subscription_repo,
        plans=app.state.plan_repo,
        counters=RedisQuotaCounter(redis_client),
        usage_store=usage_store,
        notifier=QuotaAlertMailer(
            mailer=email_sender,
            billing_profiles=app.state.tenant_billing_profile_repo,
            tenants=app.state.tenant_repo,
        ),
    )
    app.state.quota_gate = quota_gate
    app.state.get_conversation_detail_use_case = GetConversationDetailUseCase(
        conversations=conversation_repo,
        archive=ClickHouseMessageArchive(clickhouse),
        usage_store=usage_store,
        cost_rates=app.state.cost_rate_repo,
    )
    compute_statement = ComputeStatementUseCase(
        usage_store=usage_store,
        cost_rates=app.state.cost_rate_repo,
        plans=app.state.plan_repo,
        subscriptions=app.state.subscription_repo,
        statements=app.state.statement_repo,
    )
    app.state.compute_statement_use_case = compute_statement
    app.state.close_billing_period_use_case = CloseBillingPeriodUseCase(
        compute=compute_statement, subscriptions=app.state.subscription_repo, statements=app.state.statement_repo
    )
    app.state.plan_pricing_insight_use_case = PlanPricingInsightUseCase(
        usage_store=usage_store,
        cost_rates=app.state.cost_rate_repo,
        plans=app.state.plan_repo,
        subscriptions=app.state.subscription_repo,
    )
    app.state.list_unrated_meters_use_case = ListUnratedMetersUseCase(
        usage_store=usage_store, cost_rates=app.state.cost_rate_repo
    )
    app.state.get_onboarding_status_use_case = GetOnboardingStatusUseCase(
        billing_profiles=app.state.tenant_billing_profile_repo,
        users=app.state.user_repo,
        subscriptions=app.state.subscription_repo,
        plans=app.state.plan_repo,
        project_repo=app.state.project_repo,
        agent_repo=app.state.agent_repo,
        channel_connection_repo=app.state.channel_connection_repo,
        workspace=app.state.prepare_langflow_session_use_case,
        langflow=app.state.langflow_admin_client,
    )
    logger.info("billing.dependencies.initialized")

    # Outbound handler (WebSocket + native channel senders). Built
    # after the database repositories so it can be given a real
    # channel_connection_repo.
    outbound_handler = HandleOutboundResponseUseCase(
        ws_registry=ws_registry,
        channel_connection_repo=app.state.channel_connection_repo,
        channel_senders=ChannelSenderFactory().build_all(
            call_session_registry=call_session_registry,
            voice_provider=app.state.voice_provider,
            call_session_repo=app.state.call_session_repo,
        ),
        session_repo=session_repo,
        session_history_repo=session_history_repo,
        session_ttl_seconds=settings.SESSION_TTL_SECONDS,
        conversation_tracker=conversation_tracker,
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
        conversation_tracker=conversation_tracker,
        quota_gate=quota_gate,
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

        conversation_events_pub = getattr(app.state, "conversation_events_kafka_publisher", None)
        if conversation_events_pub:
            await conversation_events_pub.stop()
            logger.info("kafka.conversation_events_publisher.stopped")

    redis_client = getattr(app.state, "redis_client", None)
    if redis_client:
        await redis_client.aclose()
        logger.info("redis.client.closed")

    if settings.ENABLE_RABBITMQ:
        rabbit_pub = getattr(app.state, "rabbitmq_publisher", None)
        if rabbit_pub:
            await rabbit_pub.stop()
            logger.info("rabbitmq.publisher.stopped")

    langflow_admin_client = getattr(app.state, "langflow_admin_client", None)
    if langflow_admin_client:
        await langflow_admin_client.aclose()

    email_sender = getattr(app.state, "email_sender", None)
    if email_sender:
        await email_sender.aclose()

    clickhouse = getattr(app.state, "clickhouse", None)
    if clickhouse:
        await clickhouse.aclose()

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
instrument_fastapi_app(app)
register_error_handlers(app)


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
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(langflow_sso_router)
app.include_router(contact_router)
