"""channel_connections: tipo de canal "whatsapp_360dialog" (API oficial vía 360dialog)

Revision ID: 0017_whatsapp_360dialog_channel
Revises: 0016_contacts
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_whatsapp_360dialog_channel"
down_revision: Union[str, None] = "0016_contacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITHOUT = "'facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok','voice','webchat'"


def upgrade() -> None:
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type",
        "channel_connections",
        f"channel_type IN ({_WITHOUT},'whatsapp_360dialog')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM channel_connections WHERE channel_type = 'whatsapp_360dialog'")
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type", "channel_connections", f"channel_type IN ({_WITHOUT})"
    )
