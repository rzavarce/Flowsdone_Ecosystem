"""conversations: conversación acotada (24 h de inactividad / 7 días máx.) dentro de una sesión de Switchboard

Revision ID: 0010_conversations
Revises: 0009_user_profile
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_conversations"
down_revision: Union[str, None] = "0009_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Estado vivo de cada conversación (lo que lista la bandeja de entrada).
    # El texto de los mensajes NO va aquí: va al archivo de ClickHouse
    # (flowsdone.messages). agent_id/channel_connection_id sin FK a propósito:
    # borrar un agente o un canal no debe bloquear ni borrar el histórico.
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("channel_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inbound_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outbound_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_conversations_status"),
        sa.CheckConstraint(
            "close_reason IS NULL OR close_reason IN ('inactivity','max_duration','manual')",
            name="ck_conversations_close_reason",
        ),
    )
    # Una sola conversación abierta por sesión: dos primeros mensajes
    # simultáneos del mismo contacto no pueden abrir dos conversaciones.
    op.create_index(
        "uq_conversations_open_session",
        "conversations",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index("ix_conversations_tenant_last_message", "conversations", ["tenant_id", "last_message_at"])
    op.create_index("ix_conversations_project_last_message", "conversations", ["project_id", "last_message_at"])
    # Para el barrido periódico que cierra las conversaciones inactivas.
    op.create_index(
        "ix_conversations_open_last_inbound",
        "conversations",
        ["last_inbound_at"],
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_open_last_inbound", table_name="conversations")
    op.drop_index("ix_conversations_project_last_message", table_name="conversations")
    op.drop_index("ix_conversations_tenant_last_message", table_name="conversations")
    op.drop_index("uq_conversations_open_session", table_name="conversations")
    op.drop_table("conversations")
