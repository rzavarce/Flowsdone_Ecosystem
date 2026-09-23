"""users: agrega el rol 'consultant'; tenant_billing_profiles: datos de facturación por tenant

Revision ID: 0008_billing_and_consultant
Revises: 0007_pending_users
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_billing_and_consultant"
down_revision: Union[str, None] = "0007_pending_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLE_CHECK = "role IN ('admin','tenant_manager','botmaster','client')"
_NEW_ROLE_CHECK = "role IN ('admin','tenant_manager','botmaster','client','consultant')"


def upgrade() -> None:
    # consultant: consultores de clientes, acotados a solo reportes (ver
    # ROLE_PERMISSIONS en la PWA) - se crean como botmaster/tenant_manager,
    # desde la pantalla Usuarios.
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", _NEW_ROLE_CHECK)

    # Perfil de facturación 1:1 con un tenant. Solo captura de datos (razón
    # social, identificación fiscal, dirección, contacto, moneda, plan/ciclo
    # como texto libre) - no hay motor de cobro ni sistema de suscripciones
    # detrás; ver TenantBillingProfile (domain/models/tenant_billing_profile.py).
    op.create_table(
        "tenant_billing_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("legal_name", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.Text(), nullable=True),
        sa.Column("billing_email", sa.Text(), nullable=True),
        sa.Column("billing_contact_name", sa.Text(), nullable=True),
        sa.Column("billing_phone", sa.Text(), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state_province", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("billing_cycle", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_billing_profiles")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", _OLD_ROLE_CHECK)
