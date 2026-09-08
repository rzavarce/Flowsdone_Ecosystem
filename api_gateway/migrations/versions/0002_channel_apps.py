"""channel_apps: credenciales de la App compartida por proveedor (meta/twitter/tiktok)

Revision ID: 0002_channel_apps
Revises: 0001_initial_schema
Create Date: 2026-08-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_channel_apps"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_apps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("credentials", postgresql.JSONB(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", name="uq_channel_apps_provider"),
        sa.CheckConstraint(
            "provider IN ('meta','twitter','tiktok')",
            name="ck_channel_apps_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("channel_apps")
