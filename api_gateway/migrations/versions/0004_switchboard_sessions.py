"""session_messages/session_events: histórico de Switchboard (turno a turno y eventos de ciclo de vida)

Revision ID: 0004_switchboard
Revises: 0003_voice_twilio
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_switchboard"
down_revision: Union[str, None] = "0003_voice_twilio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("app", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound')",
            name="ck_session_messages_direction",
        ),
    )
    op.create_index(
        "ix_session_messages_session_id_created_at",
        "session_messages",
        ["session_id", "created_at"],
    )
    op.create_index("ix_session_messages_project_id", "session_messages", ["project_id"])

    op.create_table(
        "session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_app", sa.Text(), nullable=True),
        sa.Column("to_app", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('started','app_switched','closed')",
            name="ck_session_events_event_type",
        ),
    )
    op.create_index(
        "ix_session_events_session_id_created_at",
        "session_events",
        ["session_id", "created_at"],
    )
    op.create_index("ix_session_events_project_id", "session_events", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_session_events_project_id", table_name="session_events")
    op.drop_index("ix_session_events_session_id_created_at", table_name="session_events")
    op.drop_table("session_events")

    op.drop_index("ix_session_messages_project_id", table_name="session_messages")
    op.drop_index("ix_session_messages_session_id_created_at", table_name="session_messages")
    op.drop_table("session_messages")
