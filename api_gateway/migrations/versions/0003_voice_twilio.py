"""channel_connections/channel_apps: sumar el canal "voice" y el proveedor "twilio"

Revision ID: 0003_voice_twilio
Revises: 0002_channel_apps
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
# Kept short deliberately: alembic_version.version_num is VARCHAR(32)
# (see migration 0001), and alembic does not truncate/validate this at
# revision-creation time - a longer id fails at upgrade time instead.
revision: str = "0003_voice_twilio"
down_revision: Union[str, None] = "0002_channel_apps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_channel_connections_channel_type", "channel_connections", type_="check"
    )
    op.create_check_constraint(
        "ck_channel_connections_channel_type",
        "channel_connections",
        "channel_type IN ('facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok','voice')",
    )

    op.drop_constraint("ck_channel_apps_provider", "channel_apps", type_="check")
    op.create_check_constraint(
        "ck_channel_apps_provider",
        "channel_apps",
        "provider IN ('meta','twitter','tiktok','twilio')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_channel_apps_provider", "channel_apps", type_="check")
    op.create_check_constraint(
        "ck_channel_apps_provider",
        "channel_apps",
        "provider IN ('meta','twitter','tiktok')",
    )

    op.drop_constraint(
        "ck_channel_connections_channel_type", "channel_connections", type_="check"
    )
    op.create_check_constraint(
        "ck_channel_connections_channel_type",
        "channel_connections",
        "channel_type IN ('facebook','instagram','twitter','whatsapp_evolution','telegram','tiktok')",
    )
