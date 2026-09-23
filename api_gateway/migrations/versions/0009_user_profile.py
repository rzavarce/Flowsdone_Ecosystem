"""users: datos de perfil opcionales (teléfono, dirección, redes) y foto

Revision ID: 0009_user_profile
Revises: 0008_billing_and_consultant
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_user_profile"
down_revision: Union[str, None] = "0008_billing_and_consultant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Todo opcional: lo edita cada usuario desde "Mi perfil" (PATCH /me/profile)
    # o un admin desde Usuarios. social_links: {website, linkedin, x, facebook,
    # instagram} -> URL, solo las que estén cargadas.
    op.add_column("users", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("address", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "social_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Marca de la foto (cache-busting en la PWA); los bytes van en su propia
    # tabla para que listar usuarios no los arrastre.
    op.add_column("users", sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "user_avatars",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_avatars")
    op.drop_column("users", "avatar_updated_at")
    op.drop_column("users", "social_links")
    op.drop_column("users", "address")
    op.drop_column("users", "phone")
