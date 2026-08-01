"""initial multi-tenant schema (tenants, projects, agents, workflows, channel_connections, workflow_executions)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_projects_tenant_slug"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("langflow_flow_id", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_agents_project_name"),
    )
    op.create_index("ix_agents_project_id", "agents", ["project_id"])

    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("n8n_workflow_id", sa.Text(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False, server_default="webhook"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_workflows_project_name"),
    )
    op.create_index("ix_workflows_project_id", "workflows", ["project_id"])

    op.create_table(
        "channel_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("credentials", postgresql.JSONB(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("channel_type", "external_id", name="uq_channel_connections_type_external"),
        sa.CheckConstraint(
            "channel_type IN ('facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok')",
            name="ck_channel_connections_channel_type",
        ),
    )
    op.create_index("ix_channel_connections_project_id", "channel_connections", ["project_id"])

    op.create_table(
        "workflow_executions",
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_executions")
    op.drop_index("ix_channel_connections_project_id", table_name="channel_connections")
    op.drop_table("channel_connections")
    op.drop_index("ix_workflows_project_id", table_name="workflows")
    op.drop_table("workflows")
    op.drop_index("ix_agents_project_id", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("tenants")
