"""plans, tenant_subscriptions y usage_statements (planes, cuotas por canal y cierre mensual)

Revision ID: 0012_plans_and_billing
Revises: 0011_usage_metering
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_plans_and_billing"
down_revision: Union[str, None] = "0011_usage_metering"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plan: cuota fija + mensajes incluidos por canal + precio de excedente por
    # canal (JSONB {canal: n}, "*" = resto de canales). Importes en micro-unidades.
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("monthly_fee_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("included_messages", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("overage_price_micros", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("margin_pct", sa.Numeric(7, 2), nullable=False, server_default="30"),
        sa.Column("allowed_models", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("monthly_token_allowance", sa.BigInteger(), nullable=True),
        sa.Column("default_overage_mode", sa.Text(), nullable=False, server_default="notify"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "default_overage_mode IN ('notify','overage','hard_stop')", name="ck_plans_default_overage_mode"
        ),
        sa.CheckConstraint("monthly_fee_micros >= 0", name="ck_plans_fee"),
    )

    # Una suscripción por tenant. Un plan en uso no se puede borrar (RESTRICT).
    op.create_table(
        "tenant_subscriptions",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("overage_mode", sa.Text(), nullable=True),
        sa.Column("spending_cap_micros", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "overage_mode IS NULL OR overage_mode IN ('notify','overage','hard_stop')",
            name="ck_tenant_subscriptions_overage_mode",
        ),
    )

    # Extracto mensual congelado al cerrar el periodo (nunca se sobrescribe).
    op.create_table(
        "usage_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="closed"),
        sa.Column("revenue_micros", sa.BigInteger(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "period", name="uq_usage_statements_tenant_period"),
    )


def downgrade() -> None:
    op.drop_table("usage_statements")
    op.drop_table("tenant_subscriptions")
    op.drop_table("plans")
