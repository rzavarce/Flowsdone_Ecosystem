"""conversations: índice (session_id, last_inbound_at) para la ventana de mensajería

Revision ID: 0018_conv_session_last_inbound
Revises: 0017_whatsapp_360dialog_channel
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_conv_session_last_inbound"
down_revision: Union[str, None] = "0017_whatsapp_360dialog_channel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_session_last_inbound", "conversations", ["session_id", "last_inbound_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_session_last_inbound", table_name="conversations")
