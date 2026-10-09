"""CRM: integraciones por proyecto (crm_integrations) y traspasos (handoffs)

Revision ID: 0020_crm_handoffs
Revises: 0019_chatwoot_channel
Create Date: 2026-10-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0020_crm_handoffs"
down_revision: Union[str, None] = "0019_chatwoot_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("credentials", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_crm_integrations_project"),
        sa.CheckConstraint("provider IN ('generic_webhook')", name="ck_crm_integrations_provider"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_crm_integrations_status"),
    )
    op.create_index("ix_crm_integrations_tenant_id", "crm_integrations", ["tenant_id"])

    op.create_table(
        "handoffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("contact", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('open','closed','expired')", name="ck_handoffs_status"),
        sa.CheckConstraint("close_reason IS NULL OR close_reason IN ('agent','expired')", name="ck_handoffs_close_reason"),
    )
    op.create_index(
        "uq_handoffs_open_session", "handoffs", ["session_id"], unique=True, postgresql_where=sa.text("status = 'open'")
    )
    op.create_index("ix_handoffs_project_opened", "handoffs", ["project_id", "opened_at"])


def downgrade() -> None:
    op.drop_index("ix_handoffs_project_opened", table_name="handoffs")
    op.drop_index("uq_handoffs_open_session", table_name="handoffs")
    op.drop_table("handoffs")
    op.drop_index("ix_crm_integrations_tenant_id", table_name="crm_integrations")
    op.drop_table("crm_integrations")
