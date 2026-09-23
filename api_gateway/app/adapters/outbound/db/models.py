"""SQLAlchemy ORM models for the multi-tenant admin schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by all models in this module."""


class TenantModel(Base):
    """Row for a top-level tenant."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectModel(Base):
    """Row for a project, scoped to a tenant."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentModel(Base):
    """Row for a Langflow agent, scoped to a project."""

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_agents_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    langflow_flow_id: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowConfigModel(Base):
    """Row for an n8n workflow trigger configuration, scoped to a project."""

    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_workflows_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    n8n_workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False, default="webhook")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelConnectionModel(Base):
    """Row for a channel connected to a project (WhatsApp/Facebook/
    Instagram/Telegram/X/TikTok account), unique per (channel_type,
    external_id).
    """

    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint(
            "channel_type", "external_id", name="uq_channel_connections_type_external"
        ),
        CheckConstraint(
            "channel_type IN ('facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok')",
            name="ck_channel_connections_channel_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChannelAppModel(Base):
    """Row for a provider's shared app credentials (meta/twitter/tiktok),
    global for the whole SaaS. Not to be confused with
    ChannelConnectionModel, which is per project/client.
    """

    __tablename__ = "channel_apps"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_channel_apps_provider"),
        CheckConstraint(
            "provider IN ('meta','twitter','tiktok')",
            name="ck_channel_apps_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowExecutionModel(Base):
    """Row used for idempotency tracking.

    This table predates Alembic (originally created by
    scripts/init-db.sh) and is incorporated here with the same
    names/types expected by
    adapters/outbound/db/idempotency_repository.py, which accesses it
    through raw asyncpg rather than through this model.
    """

    __tablename__ = "workflow_executions"

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionMessageModel(Base):
    """Row for one turn of a Switchboard conversation - the durable,
    append-only transcript (SessionRepositoryPort in Redis is the fast,
    ephemeral counterpart, not the source of truth for history).
    """

    __tablename__ = "session_messages"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_session_messages_direction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    app: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionEventModel(Base):
    """Row for one Switchboard lifecycle event (session started, app
    switched, session closed) - the audit trail of routing decisions.
    """

    __tablename__ = "session_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('started','app_switched','closed')", name="ck_session_events_event_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_app: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_app: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationModel(Base):
    """Row for one Conversation - the live, mutable record an inbox lists
    and filters (status, counters, timestamps). Message bodies are not
    here: they live in the ClickHouse archive (MessageArchivePort).

    agent_id/channel_connection_id carry no foreign key on purpose:
    deleting an agent or a channel connection must neither block on nor
    erase the conversation history recorded under it.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_conversations_status"),
        CheckConstraint(
            "close_reason IS NULL OR close_reason IN ('inactivity','max_duration','manual')",
            name="ck_conversations_close_reason",
        ),
        # At most one open conversation per session (see
        # ConversationRepositoryPort.open).
        Index(
            "uq_conversations_open_session",
            "session_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_conversations_tenant_last_message", "tenant_id", "last_message_at"),
        Index("ix_conversations_project_last_message", "project_id", "last_message_at"),
        Index("ix_conversations_open_last_inbound", "last_inbound_at", postgresql_where=text("status = 'open'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    channel_connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contact: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_inbound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inbound_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CostRateModel(Base):
    """Row for one version of what Flowsdone pays for a meter (see
    domain/models/usage.py CostRate). Append-only: a price change is a
    new row with a later valid_from."""

    __tablename__ = "cost_rates"
    __table_args__ = (
        CheckConstraint("kind IN ('channel','llm','platform')", name="ck_cost_rates_kind"),
        CheckConstraint("price_micros >= 0 AND per_quantity > 0", name="ck_cost_rates_amounts"),
        Index("ix_cost_rates_meter", "kind", "unit", "provider", "sku", "valid_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    price_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    per_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="EUR")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyncCursorModel(Base):
    """Row remembering up to when a periodic sync processed its source."""

    __tablename__ = "sync_cursors"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    position: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlanModel(Base):
    """Row for a commercial plan (see domain/models/billing.py Plan)."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "default_overage_mode IN ('notify','overage','hard_stop')", name="ck_plans_default_overage_mode"
        ),
        CheckConstraint("monthly_fee_micros >= 0", name="ck_plans_fee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_fee_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="EUR")
    included_messages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overage_price_micros: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    margin_pct: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, default=30)
    allowed_models: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    monthly_token_allowance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    default_overage_mode: Mapped[str] = mapped_column(Text, nullable=False, default="notify")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantSubscriptionModel(Base):
    """Row for a tenant's plan (at most one per tenant). A plan in use
    cannot be deleted (RESTRICT)."""

    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "overage_mode IS NULL OR overage_mode IN ('notify','overage','hard_stop')",
            name="ck_tenant_subscriptions_overage_mode",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    overage_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    spending_cap_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UsageStatementModel(Base):
    """Row for a closed (frozen) monthly statement; `data` holds the whole
    BillingStatement, the numeric columns are there for listing/reporting."""

    __tablename__ = "usage_statements"
    __table_args__ = (UniqueConstraint("tenant_id", "period", name="uq_usage_statements_tenant_period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="closed")
    revenue_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserModel(Base):
    """Row for a console user (see `domain.models.user.User`)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','tenant_manager','botmaster','client')",
            name="ck_users_role",
        ),
        CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_links: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Case-insensitive unique email. Declared here for parity with the
# migration (0005_users), which is what actually creates it.
Index("uq_users_email_lower", func.lower(UserModel.email), unique=True)


class UserAvatarModel(Base):
    """A user's profile photo (1:1 with `users`, bytes kept out of the user row)."""

    __tablename__ = "user_avatars"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserTenantModel(Base):
    """Membership of a user in a tenant (admins need no rows: they see all)."""

    __tablename__ = "user_tenants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LangflowAccountModel(Base):
    """Row for the Langflow user that stands for a tenant (password encrypted)."""

    __tablename__ = "langflow_accounts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    credentials: Mapped[dict] = mapped_column(JSONB, nullable=False)
    langflow_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LangflowFolderModel(Base):
    """Row linking a gateway project to its folder in the tenant's Langflow."""

    __tablename__ = "langflow_folders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    folder_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantBillingProfileModel(Base):
    """Row for a tenant's billing/company data (1:1 - pure data capture, no
    billing engine behind it; see domain/models/tenant_billing_profile.py)."""

    __tablename__ = "tenant_billing_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    legal_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_contact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_province: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_cycle: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
