"""SQLAlchemy ORM models for the multi-tenant admin schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
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
