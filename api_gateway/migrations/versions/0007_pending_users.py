"""users: agrega el status 'pending' (activación de cuenta por email)

Revision ID: 0007_pending_users
Revises: 0006_langflow_sso
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_pending_users"
down_revision: Union[str, None] = "0006_langflow_sso"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_CHECK = "status IN ('active','disabled')"
_NEW_CHECK = "status IN ('pending','active','disabled')"


def upgrade() -> None:
    # Postgres no soporta ALTER CHECK: hay que quitar la restricción vieja y
    # crear la nueva. Un usuario recién creado queda en 'pending' hasta que
    # activa su cuenta por email (ver ProvisionUserUseCase / ActivateAccountUseCase);
    # ni CreateUserUseCase ni UpdateUserUseCase dejan poner 'pending' a mano,
    # solo lo hace la creación.
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.create_check_constraint("ck_users_status", "users", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.create_check_constraint("ck_users_status", "users", _OLD_CHECK)
