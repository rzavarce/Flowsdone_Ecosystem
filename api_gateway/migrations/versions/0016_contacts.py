"""contacts: ficha del contacto de las conversaciones (nombre, email, teléfono, usuario, notas)

Revision ID: 0016_contacts
Revises: 0015_webchat_share_links
Create Date: 2026-09-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_contacts"
down_revision: Union[str, None] = "0015_webchat_share_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "channel_type", "identifier", name="uq_contacts_identity"),
    )
    # A card for every contact that already has conversations, so the contact
    # list isn't empty until they write again. What the identifier tells:
    # a WhatsApp jid or a caller's number is a phone; a browser call's
    # identity is its (generic, renameable) name.
    op.execute(
        r"""
        INSERT INTO contacts (id, tenant_id, channel_type, identifier, name, phone, created_at, updated_at)
        SELECT gen_random_uuid(), tenant_id, channel_type, contact,
               CASE WHEN contact LIKE 'client:%' THEN contact END,
               CASE
                   WHEN channel_type = 'whatsapp_evolution' AND contact ~ '^[0-9]+@s\.whatsapp\.net$'
                       THEN '+' || split_part(contact, '@', 1)
                   WHEN channel_type = 'voice' AND contact ~ '^\+[0-9]+$' THEN contact
               END,
               min(started_at), now()
        FROM conversations
        GROUP BY tenant_id, channel_type, contact
        ON CONFLICT ON CONSTRAINT uq_contacts_identity DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("contacts")
