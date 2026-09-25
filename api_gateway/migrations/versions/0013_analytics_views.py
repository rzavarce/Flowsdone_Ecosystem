"""schema analytics: vistas de solo lectura para Metabase

Metabase (dashboards y reportes) solo puede leer este esquema, con el rol
metabase_reader (scripts/metabase/init-postgres.sh). Las vistas dejan fuera
lo sensible: contraseñas y datos personales de los usuarios, credenciales e
identificadores de los canales (el external_id de Telegram es el token del
bot), la config de los agentes, las cuentas de Langflow y el contacto de las
conversaciones. Todas llevan tenant_id para poder filtrar por tenant.

Revision ID: 0013_analytics_views
Revises: 0012_plans_and_billing
Create Date: 2026-09-25

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_analytics_views"
down_revision: Union[str, None] = "0012_plans_and_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VIEWS = {
    "tenants": """
        SELECT id AS tenant_id, name, slug, status, created_at
        FROM public.tenants
    """,
    "projects": """
        SELECT id AS project_id, tenant_id, name, status, created_at
        FROM public.projects
    """,
    "agents": """
        SELECT a.id AS agent_id, p.tenant_id, a.project_id, a.name, a.is_default, a.status, a.created_at
        FROM public.agents a JOIN public.projects p ON p.id = a.project_id
    """,
    "channel_connections": """
        SELECT c.id AS channel_connection_id, p.tenant_id, c.project_id, c.agent_id, c.channel_type,
               c.display_name, c.status, c.created_at
        FROM public.channel_connections c JOIN public.projects p ON p.id = c.project_id
    """,
    "conversations": """
        SELECT id AS conversation_id, tenant_id, project_id, agent_id, channel_type, channel_connection_id,
               status, started_at, last_inbound_at, last_message_at, inbound_count, outbound_count,
               closed_at, close_reason
        FROM public.conversations
    """,
    "users": """
        SELECT u.id AS user_id, ut.tenant_id, u.role, u.status, u.last_login_at, u.created_at
        FROM public.users u LEFT JOIN public.user_tenants ut ON ut.user_id = u.id
    """,
    "plans": """
        SELECT id AS plan_id, code, name, monthly_fee_micros, currency, included_messages,
               monthly_token_allowance, active
        FROM public.plans
    """,
    "subscriptions": """
        SELECT s.tenant_id, s.plan_id, p.code AS plan_code, p.name AS plan_name, p.monthly_fee_micros,
               s.overage_mode, s.spending_cap_micros, s.started_at
        FROM public.tenant_subscriptions s JOIN public.plans p ON p.id = s.plan_id
    """,
    "usage_statements": """
        SELECT tenant_id, period, status, revenue_micros, cost_micros, created_at
        FROM public.usage_statements
    """,
    "session_events": """
        SELECT e.id AS event_id, p.tenant_id, e.project_id, e.event_type, e.from_app, e.to_app, e.created_at
        FROM public.session_events e JOIN public.projects p ON p.id = e.project_id
    """,
}


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    for name, query in VIEWS.items():
        op.execute(f"CREATE OR REPLACE VIEW analytics.{name} AS {query}")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
