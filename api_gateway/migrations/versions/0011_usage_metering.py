"""cost_rates (catálogo de costes versionado) y sync_cursors (posición de las sincronizaciones periódicas)

Revision ID: 0011_usage_metering
Revises: 0010_conversations
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011_usage_metering"
down_revision: Union[str, None] = "0010_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lo que paga Flowsdone por cada contador (mensaje de un canal, token de un
    # modelo...). Solo se insertan filas: un cambio de precio es una fila nueva
    # con valid_from posterior, así el consumo pasado se sigue valorando con el
    # precio que tenía. Importes en micro-unidades enteras (1 EUR = 1_000_000).
    op.create_table(
        "cost_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("price_micros", sa.BigInteger(), nullable=False),
        sa.Column("per_quantity", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="EUR"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('channel','llm','platform')", name="ck_cost_rates_kind"),
        sa.CheckConstraint("price_micros >= 0 AND per_quantity > 0", name="ck_cost_rates_amounts"),
    )
    op.create_index("ix_cost_rates_meter", "cost_rates", ["kind", "unit", "provider", "sku", "valid_from"])

    op.create_table(
        "sync_cursors",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("position", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_cursors")
    op.drop_index("ix_cost_rates_meter", table_name="cost_rates")
    op.drop_table("cost_rates")
