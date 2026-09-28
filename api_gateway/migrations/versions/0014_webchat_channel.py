"""channel_connections: tipo de canal "webchat" (chat web de cada tenant)

Revision ID: 0014_webchat_channel
Revises: 0013_analytics_views
Create Date: 2026-09-26

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_webchat_channel"
down_revision: Union[str, None] = "0013_analytics_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITHOUT = "'facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok','voice'"


def upgrade() -> None:
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type",
        "channel_connections",
        f"channel_type IN ({_WITHOUT},'webchat')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM channel_connections WHERE channel_type = 'webchat'")
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type", "channel_connections", f"channel_type IN ({_WITHOUT})"
    )
