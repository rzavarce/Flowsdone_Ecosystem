"""The console's Metabase dashboards, as code (created/updated by provision.py).

Every question is native SQL over the read-only sources:
- ClickHouse `flowsdone.messages` / `flowsdone.usage_events` (quantities in
  real time: messages, response times, tokens);
- Postgres `analytics.*` views (conversations, users, plans, and the monthly
  statements - the only money shown, frozen at month close).

Each dashboard has two filters:
- `tenant`: LOCKED in the signed embed URL by the gateway (the viewer can't
  change it; an empty list means every tenant the viewer may see);
- `fecha`: a date range the viewer can change (last 30 days by default).

Dashboards are identified by a marker in their description
(`[flowsdone:<key>]`), which the gateway uses to find their id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

CH = "clickhouse"
PG = "postgres"
COLLECTION = "Consola Flowsdone (gestionado)"
COLLECTION_DESCRIPTION = (
    "Dashboards de la consola, creados por scripts/metabase/provision.py. "
    "No los edites aquí: cada despliegue los vuelve a dejar como están en el código."
)

# Field filters: template tag -> "schema.table.column" of the source.
MSG = {"tenant": "flowsdone.messages.tenant_id", "fecha": "flowsdone.messages.ts"}
USAGE = {"tenant": "flowsdone.usage_events.tenant_id", "fecha": "flowsdone.usage_events.ts"}
CONV = {"tenant": "analytics.conversations.tenant_id", "fecha": "analytics.conversations.started_at"}

CHANNEL_LABEL = """multiIf(channel_type = 'whatsapp_evolution', 'WhatsApp', channel_type = 'instagram', 'Instagram',
    channel_type = 'facebook', 'Messenger', channel_type = 'telegram', 'Telegram', channel_type = 'voice', 'Voz',
    channel_type = 'webchat', 'Chat web', channel_type = 'twitter', 'X', channel_type = 'tiktok', 'TikTok', channel_type)"""

# Agent response time: seconds between a customer message and the agent's reply.
RESPONSE_TIMES = """
    SELECT toDate(ts, 'Europe/Madrid') AS day, delay FROM (
        SELECT ts, direction,
               lagInFrame(direction) OVER w AS previous_direction,
               dateDiff('millisecond', lagInFrame(ts) OVER w, ts) / 1000 AS delay
        FROM flowsdone.messages
        WHERE {{tenant}} AND {{fecha}}
        WINDOW w AS (PARTITION BY conversation_id ORDER BY ts ROWS BETWEEN 1 PRECEDING AND CURRENT ROW)
    )
    WHERE direction = 'outbound' AND previous_direction = 'inbound'
"""


@dataclass(frozen=True)
class Card:
    """A saved question.

    Attributes:
        name (str): Title shown on the dashboard (unique in the collection).
        source (str): CH or PG.
        sql (str): Native query, with {{tenant}} / {{fecha}} field filters.
        display (str): Metabase visualization (scalar, line, bar, pie, table…).
        tags (Dict[str, str]): Template tag -> field ("schema.table.column").
        settings (Dict): Visualization settings.
    """

    name: str
    source: str
    sql: str
    display: str
    tags: Dict[str, str]
    settings: Dict = field(default_factory=dict)


def _line(x: str, *ys: str, stacked: bool = False, display: str = "line") -> Dict:
    """Visualization settings for a line/bar chart.

    Args:
        x (str): Dimension column.
        *ys (str): Metric columns.
        stacked (bool): Stack the series.
        display (str): Unused marker for readability.

    Returns:
        Dict: Settings.
    """
    settings = {"graph.dimensions": [x], "graph.metrics": list(ys)}
    if stacked:
        settings["stackable.stack_type"] = "stacked"
    return settings


CARDS: Dict[str, Card] = {
    # ------------------------------------------------------------ activity
    "conversations": Card(
        "Conversaciones", CH,
        "SELECT uniqExact(conversation_id) AS conversaciones FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}}",
        "scalar", MSG,
    ),
    "answered": Card(
        "Mensajes respondidos", CH,
        "SELECT countIf(direction = 'outbound') AS respondidos FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}}",
        "scalar", MSG,
    ),
    "received": Card(
        "Mensajes recibidos", CH,
        "SELECT countIf(direction = 'inbound') AS recibidos FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}}",
        "scalar", MSG,
    ),
    "active_tenants": Card(
        "Tenants con actividad", CH,
        "SELECT uniqExact(tenant_id) AS tenants FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}}",
        "scalar", MSG,
    ),
    "daily_volume": Card(
        "Conversaciones y mensajes por día", CH,
        """SELECT toDate(ts, 'Europe/Madrid') AS "Día", uniqExact(conversation_id) AS "Conversaciones",
               countIf(direction = 'outbound') AS "Mensajes respondidos"
           FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 1""",
        "line", MSG, _line("Día", "Conversaciones", "Mensajes respondidos"),
    ),
    "by_channel": Card(
        "Mensajes por canal", CH,
        f"""SELECT {CHANNEL_LABEL} AS "Canal", count() AS "Mensajes"
            FROM flowsdone.messages WHERE {{{{tenant}}}} AND {{{{fecha}}}} GROUP BY 1 ORDER BY 2 DESC""",
        "pie", MSG, {"pie.dimension": "Canal", "pie.metric": "Mensajes"},
    ),
    "by_hour": Card(
        "Mensajes recibidos por hora del día", CH,
        """SELECT toHour(ts, 'Europe/Madrid') AS "Hora", countIf(direction = 'inbound') AS "Mensajes"
           FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 1""",
        "bar", MSG, _line("Hora", "Mensajes"),
    ),
    "by_weekday": Card(
        "Mensajes recibidos por día de la semana", CH,
        """SELECT toDayOfWeek(ts, 0, 'Europe/Madrid') AS n,
               ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][n] AS "Día",
               countIf(direction = 'inbound') AS "Mensajes"
           FROM flowsdone.messages WHERE {{tenant}} AND {{fecha}} GROUP BY n ORDER BY n""",
        "bar", MSG, {**_line("Día", "Mensajes"), "table.columns": [{"name": "n", "enabled": False}]},
    ),
    "top_tenants": Card(
        "Tenants con más conversaciones", PG,
        """SELECT tenants.name AS "Tenant", count(*) AS "Conversaciones",
                  sum(conversations.inbound_count + conversations.outbound_count) AS "Mensajes"
           FROM analytics.conversations JOIN analytics.tenants ON tenants.tenant_id = conversations.tenant_id
           WHERE {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 2 DESC LIMIT 10""",
        "table", CONV,
    ),
    "by_agent": Card(
        "Conversaciones por agente", PG,
        """SELECT agents.name AS "Agente", count(*) AS "Conversaciones",
                  round(avg(conversations.inbound_count + conversations.outbound_count), 1) AS "Mensajes por conversación"
           FROM analytics.conversations JOIN analytics.agents ON agents.agent_id = conversations.agent_id
           WHERE {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 2 DESC""",
        "table", CONV,
    ),
    "open_conversations": Card(
        "Conversaciones abiertas ahora", PG,
        "SELECT count(*) AS abiertas FROM analytics.conversations WHERE {{tenant}} AND conversations.status = 'open'",
        "scalar", {"tenant": CONV["tenant"]},
    ),
    # ------------------------------------------------------------ performance
    "response_p50": Card(
        "Tiempo de respuesta (mediana)", CH,
        f"SELECT round(quantileExact(0.5)(delay), 1) AS segundos FROM ({RESPONSE_TIMES})",
        "scalar", MSG, {"column_settings": {'["name","segundos"]': {"suffix": " s"}}},
    ),
    "response_p95": Card(
        "Tiempo de respuesta (p95)", CH,
        f"SELECT round(quantileExact(0.95)(delay), 1) AS segundos FROM ({RESPONSE_TIMES})",
        "scalar", MSG, {"column_settings": {'["name","segundos"]': {"suffix": " s"}}},
    ),
    "response_daily": Card(
        "Tiempo de respuesta por día (segundos)", CH,
        f"""SELECT day AS "Día", round(quantileExact(0.5)(delay), 1) AS "Mediana",
                   round(quantileExact(0.95)(delay), 1) AS "p95"
            FROM ({RESPONSE_TIMES}) GROUP BY 1 ORDER BY 1""",
        "line", MSG, _line("Día", "Mediana", "p95"),
    ),
    "messages_per_conversation": Card(
        "Mensajes por conversación", PG,
        """SELECT round(avg(conversations.inbound_count + conversations.outbound_count), 1) AS mensajes
           FROM analytics.conversations WHERE {{tenant}} AND {{fecha}}""",
        "scalar", CONV,
    ),
    "conversation_minutes": Card(
        "Duración media de la conversación", PG,
        """SELECT round(avg(extract(epoch FROM conversations.last_message_at - conversations.started_at)) / 60, 1) AS minutos
           FROM analytics.conversations WHERE {{tenant}} AND {{fecha}}""",
        "scalar", CONV, {"column_settings": {'["name","minutos"]': {"suffix": " min"}}},
    ),
    "close_reasons": Card(
        "Cómo terminan las conversaciones", PG,
        """SELECT CASE conversations.close_reason WHEN 'inactivity' THEN 'Inactividad (24 h)'
                    WHEN 'max_duration' THEN 'Duración máxima' WHEN 'manual' THEN 'Cierre manual'
                    ELSE 'Abiertas' END AS "Motivo", count(*) AS "Conversaciones"
           FROM analytics.conversations WHERE {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 2 DESC""",
        "pie", CONV, {"pie.dimension": "Motivo", "pie.metric": "Conversaciones"},
    ),
    # ------------------------------------------------------------ AI usage
    "tokens_daily": Card(
        "Tokens de IA por día", CH,
        """SELECT toDate(ts, 'Europe/Madrid') AS "Día",
                  sumIf(quantity, unit = 'input_token') AS "Entrada",
                  sumIf(quantity, unit = 'cached_input_token') AS "Entrada en caché",
                  sumIf(quantity, unit = 'output_token') AS "Salida"
           FROM flowsdone.usage_events WHERE kind = 'llm' AND {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 1""",
        "bar", USAGE, _line("Día", "Entrada", "Entrada en caché", "Salida", stacked=True),
    ),
    "tokens_by_model": Card(
        "Tokens por modelo", CH,
        """SELECT sku AS "Modelo", sumIf(quantity, unit = 'input_token') AS "Entrada",
                  sumIf(quantity, unit = 'cached_input_token') AS "Entrada en caché",
                  sumIf(quantity, unit = 'output_token') AS "Salida",
                  uniqExact(conversation_id) AS "Conversaciones"
           FROM flowsdone.usage_events WHERE kind = 'llm' AND {{tenant}} AND {{fecha}} GROUP BY 1 ORDER BY 2 DESC""",
        "table", USAGE,
    ),
    "tokens_per_reply": Card(
        "Tokens por respuesta", CH,
        """SELECT round(sumIf(quantity, kind = 'llm' AND unit IN ('input_token', 'output_token'))
                        / nullIf(countIf(kind = 'platform' AND sku = 'ai_message'), 0)) AS tokens
           FROM flowsdone.usage_events WHERE {{tenant}} AND {{fecha}}""",
        "scalar", USAGE,
    ),
    # ------------------------------------------------------------ console usage
    "console_users": Card(
        "Usuarios de la consola", PG,
        """SELECT CASE users.role WHEN 'admin' THEN 'Administradores' WHEN 'tenant_manager' THEN 'Gestores'
                    WHEN 'botmaster' THEN 'Botmasters' WHEN 'consultant' THEN 'Consultores'
                    WHEN 'client' THEN 'Clientes' ELSE users.role END AS "Perfil",
                  count(DISTINCT users.user_id) FILTER (WHERE users.last_login_at >= now() - interval '7 days') AS "Activos 7 días",
                  count(DISTINCT users.user_id) FILTER (WHERE users.last_login_at >= now() - interval '30 days') AS "Activos 30 días",
                  count(DISTINCT users.user_id) FILTER (WHERE users.status = 'pending') AS "Sin activar",
                  count(DISTINCT users.user_id) AS "Total"
           FROM analytics.users WHERE {{tenant}} GROUP BY 1 ORDER BY 5 DESC""",
        "table", {"tenant": "analytics.users.tenant_id"},
    ),
    # ------------------------------------------------------------ business (admin)
    "monthly_fees": Card(
        "Cuotas mensuales contratadas", PG,
        """SELECT coalesce(sum(subscriptions.monthly_fee_micros), 0) / 1000000.0 AS euros
           FROM analytics.subscriptions WHERE {{tenant}}""",
        "scalar", {"tenant": "analytics.subscriptions.tenant_id"},
        {"column_settings": {'["name","euros"]': {"number_style": "currency", "currency": "EUR"}}},
    ),
    "clients_by_plan": Card(
        "Clientes por plan", PG,
        """SELECT subscriptions.plan_name AS "Plan", count(*) AS "Clientes"
           FROM analytics.subscriptions WHERE {{tenant}} GROUP BY 1 ORDER BY 2 DESC""",
        "bar", {"tenant": "analytics.subscriptions.tenant_id"}, _line("Plan", "Clientes"),
    ),
    "monthly_statements": Card(
        "Ingresos, coste y margen por mes (meses cerrados)", PG,
        """SELECT usage_statements.period AS "Mes",
                  sum(usage_statements.revenue_micros) / 1000000.0 AS "Ingresos",
                  sum(usage_statements.cost_micros) / 1000000.0 AS "Coste",
                  sum(usage_statements.revenue_micros - usage_statements.cost_micros) / 1000000.0 AS "Margen"
           FROM analytics.usage_statements WHERE {{tenant}} GROUP BY 1 ORDER BY 1""",
        "bar", {"tenant": "analytics.usage_statements.tenant_id"}, _line("Mes", "Ingresos", "Coste", "Margen"),
    ),
    # ------------------------------------------------------------ client plan
    "plan_usage": Card(
        "Consumo del plan este mes", PG,
        """SELECT subscriptions.plan_name AS "Plan",
                  (plans.included_messages ->> '*')::int AS "Mensajes incluidos",
                  coalesce(sum(conversations.outbound_count), 0)::int AS "Mensajes respondidos",
                  round(100.0 * coalesce(sum(conversations.outbound_count), 0)
                        / nullif((plans.included_messages ->> '*')::int, 0), 1) AS "% usado"
           FROM analytics.subscriptions
           JOIN analytics.plans ON plans.plan_id = subscriptions.plan_id
           LEFT JOIN analytics.conversations ON conversations.tenant_id = subscriptions.tenant_id
                 AND conversations.started_at >= date_trunc('month', now())
           WHERE {{tenant}}
           GROUP BY 1, 2""",
        "table", {"tenant": "analytics.subscriptions.tenant_id"},
    ),
}

# A dashboard item: a card key with its width and height (grid of 24
# columns), or a heading string.
Item = Union[str, Tuple[str, int, int]]


@dataclass(frozen=True)
class Dashboard:
    """A dashboard of the console.

    Attributes:
        key (str): Stable id the gateway asks for ("platform", "client"…).
        name (str): Title.
        description (str): Shown in Metabase (the key marker is added).
        items (List[Item]): Headings and cards, laid out left to right.
    """

    key: str
    name: str
    description: str
    items: List[Item]

    @property
    def marker(self) -> str:
        """The description marker the gateway looks for."""
        return f"[flowsdone:{self.key}]"


_PLATFORM_ITEMS: List[Item] = [
    "Actividad",
    ("conversations", 6, 3), ("answered", 6, 3), ("received", 6, 3), ("active_tenants", 6, 3),
    ("daily_volume", 14, 6), ("by_channel", 10, 6),
    ("top_tenants", 12, 6), ("close_reasons", 12, 6),
    "Rendimiento",
    ("response_p50", 6, 3), ("response_p95", 6, 3), ("messages_per_conversation", 6, 3), ("conversation_minutes", 6, 3),
    ("response_daily", 24, 6),
    "Consumo de IA",
    ("tokens_per_reply", 6, 6), ("tokens_daily", 18, 6),
    ("tokens_by_model", 24, 4),
    "Uso de la consola",
    ("open_conversations", 6, 4), ("console_users", 18, 4),
]

DASHBOARDS: List[Dashboard] = [
    Dashboard(
        "platform", "Plataforma",
        "Rendimiento y uso de la plataforma para el equipo de Flowsdone.",
        _PLATFORM_ITEMS,
    ),
    Dashboard(
        "platform_admin", "Plataforma (administración)",
        "Rendimiento y uso de la plataforma, con el negocio (solo administradores).",
        _PLATFORM_ITEMS + [
            "Negocio",
            ("monthly_fees", 6, 5), ("clients_by_plan", 18, 5),
            ("monthly_statements", 24, 6),
        ],
    ),
    Dashboard(
        "client", "Tu asistente",
        "La actividad de tus asistentes: conversaciones, canales, horarios y consumo del plan.",
        [
            ("conversations", 6, 3), ("answered", 6, 3), ("response_p50", 6, 3), ("messages_per_conversation", 6, 3),
            ("plan_usage", 24, 3),
            ("daily_volume", 14, 6), ("by_channel", 10, 6),
            ("by_hour", 12, 6), ("by_weekday", 12, 6),
            ("by_agent", 12, 5), ("response_daily", 12, 5),
        ],
    ),
]

PARAMETERS = [
    {"id": "tenant", "name": "Tenant", "slug": "tenant", "type": "string/=", "sectionId": "string"},
    {"id": "fecha", "name": "Periodo", "slug": "fecha", "type": "date/all-options", "sectionId": "date",
     "default": "past30days"},
]
EMBEDDING_PARAMS = {"tenant": "locked", "fecha": "enabled"}


def layout(items: List[Item]) -> List[Tuple[Optional[str], Optional[str], int, int, int, int]]:
    """Place the items on the 24-column grid, filling rows left to right.

    Args:
        items (List[Item]): Headings and (card key, width, height).

    Returns:
        List[Tuple]: (card key or None, heading text or None, row, col, width, height).
    """
    placed, row, col, row_height = [], 0, 0, 0
    for item in items:
        if isinstance(item, str):
            key, heading, width, height = None, item, 24, 1
        else:
            key, heading = item[0], None
            width, height = item[1], item[2]
        if col + width > 24:
            row, col, row_height = row + row_height, 0, 0
        placed.append((key, heading, row, col, width, height))
        col += width
        row_height = max(row_height, height)
        if col >= 24:
            row, col, row_height = row + row_height, 0, 0
    return placed
