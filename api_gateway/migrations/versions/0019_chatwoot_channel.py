"""Chatwoot: tipo de canal "chatwoot" y proveedor compartido "chatwoot"

Revision ID: 0019_chatwoot_channel
Revises: 0018_conv_session_last_inbound
Create Date: 2026-10-03

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_chatwoot_channel"
down_revision: Union[str, None] = "0018_conv_session_last_inbound"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHANNELS = "'facebook','instagram','twitter','whatsapp_evolution','whatsapp_360dialog','telegram','tiktok','voice','webchat'"
_PROVIDERS = "'meta','twitter','tiktok','twilio'"


def upgrade() -> None:
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type", "channel_connections", f"channel_type IN ({_CHANNELS},'chatwoot')"
    )
    op.drop_constraint("ck_channel_apps_provider", "channel_apps", type_="check")
    op.create_check_constraint("ck_channel_apps_provider", "channel_apps", f"provider IN ({_PROVIDERS},'chatwoot')")


def downgrade() -> None:
    op.execute("DELETE FROM channel_connections WHERE channel_type = 'chatwoot'")
    op.execute("DELETE FROM channel_apps WHERE provider = 'chatwoot'")
    op.drop_constraint("ck_channel_connections_channel_type", "channel_connections", type_="check")
    op.create_check_constraint(
        "ck_channel_connections_channel_type", "channel_connections", f"channel_type IN ({_CHANNELS})"
    )
    op.drop_constraint("ck_channel_apps_provider", "channel_apps", type_="check")
    op.create_check_constraint("ck_channel_apps_provider", "channel_apps", f"provider IN ({_PROVIDERS})")
