"""Seed realistic demo analytics data (DEVELOPMENT ONLY).

Fills the local stack with conversations (Postgres), messages and usage
events (ClickHouse) for the tenants that already have a project with agents
and channels, so the Metabase dashboards have something to show. Everything
it writes is tagged (session_id / trace_id starting with "seed:") and can be
removed with --clear.

Run inside the api container (it has the database URLs):

    docker compose run --rm --no-deps -v ./scripts/dev:/scripts/dev api \
        python /scripts/dev/seed_analytics.py [--days 60] [--clear]

Refuses to run when PUBLIC_BASE_URL is https (production).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SEED_TAG = "seed:"
MODEL = "gpt-4.1-mini"
# Relative weight of each hour of the day (Europe/Madrid business hours peak).
HOUR_WEIGHTS = [1, 1, 0.5, 0.5, 0.5, 1, 2, 4, 7, 9, 10, 10, 9, 8, 7, 8, 9, 9, 8, 6, 5, 4, 3, 2]
CLOSE_REASONS = ["inactivity"] * 8 + ["manual"] + ["max_duration"]


@dataclass(frozen=True)
class Channel:
    """A channel connection to generate traffic on.

    Attributes:
        tenant_id (str): Its tenant.
        project_id (str): Its project.
        agent_id (str): The agent that answers it.
        connection_id (str): The channel connection.
        channel_type (str): e.g. whatsapp_evolution, telegram, voice.
    """

    tenant_id: str
    project_id: str
    agent_id: str
    connection_id: str
    channel_type: str


def guard() -> None:
    """Refuse to run against production.

    Raises:
        SystemExit: If PUBLIC_BASE_URL looks like production.
    """
    if os.environ.get("PUBLIC_BASE_URL", "").startswith("https://"):
        sys.exit("seed_analytics: PUBLIC_BASE_URL es https (producción). Este script es solo para desarrollo.")


def clickhouse(client: httpx.Client, query: str, rows: List[Dict] | None = None) -> str:
    """Run a query (or an insert with JSONEachRow rows) as the app user.

    Args:
        client (httpx.Client): Client pointing at ClickHouse's HTTP interface.
        query (str): SQL.
        rows (List[Dict] | None): Rows for an INSERT ... FORMAT JSONEachRow.

    Returns:
        str: Response body.
    """
    body = "\n".join(json.dumps(r, default=str) for r in rows) if rows else None
    response = client.post("/", params={"query": query}, content=body)
    response.raise_for_status()
    return response.text


def ts(value: datetime) -> str:
    """ClickHouse DateTime64(3) literal in UTC.

    Args:
        value (datetime): Aware datetime.

    Returns:
        str: 'YYYY-MM-DD hh:mm:ss.fff'.
    """
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def response_seconds(channel_type: str) -> float:
    """A realistic agent response time (log-normal, voice is faster).

    Args:
        channel_type (str): The channel.

    Returns:
        float: Seconds.
    """
    median = 1.8 if channel_type == "voice" else 4.0
    return min(90.0, random.lognormvariate(math.log(median), 0.6))


def build(channels: List[Channel], days: int) -> tuple[list, list, list]:
    """Generate conversations, messages and usage events.

    Args:
        channels (List[Channel]): Where traffic happens.
        days (int): How many days back.

    Returns:
        tuple[list, list, list]: (Postgres conversation rows, ClickHouse
        message rows, ClickHouse usage rows).
    """
    now = datetime.now(timezone.utc)
    conversations, messages, usage = [], [], []
    weights = {"whatsapp_evolution": 6, "instagram": 3, "telegram": 2, "facebook": 2, "voice": 2}
    for day in range(days, -1, -1):
        date = (now - timedelta(days=day)).replace(minute=0, second=0, microsecond=0)
        growth = 0.6 + 0.4 * (days - day) / max(days, 1)  # traffic grows over time
        weekend = 0.55 if date.weekday() >= 5 else 1.0
        for ch in channels:
            per_day = int(random.gauss(14, 4) * weights.get(ch.channel_type, 1) * growth * weekend / 3)
            for _ in range(max(per_day, 0)):
                hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
                start = date.replace(hour=hour) + timedelta(seconds=random.randint(0, 3599))
                if start > now:
                    continue
                conv_id, session = str(uuid.uuid4()), f"{SEED_TAG}{uuid.uuid4()}"
                contact = f"+34 6{random.randint(10000000, 99999999)}"
                t = start
                turns = random.choices([1, 2, 3, 4, 5, 6, 8], weights=[18, 25, 20, 14, 10, 8, 5])[0]
                inbound = outbound = 0
                for _turn in range(turns):
                    for direction in ("inbound", "outbound"):
                        if direction == "outbound":
                            t += timedelta(seconds=response_seconds(ch.channel_type))
                        msg_id = str(uuid.uuid4())
                        messages.append({
                            "message_id": msg_id, "ts": ts(t), "tenant_id": ch.tenant_id, "project_id": ch.project_id,
                            "agent_id": ch.agent_id, "conversation_id": conv_id, "session_id": session,
                            "channel_type": ch.channel_type, "channel_connection_id": ch.connection_id,
                            "direction": direction, "sender_type": "contact" if direction == "inbound" else "agent",
                            "app": ch.channel_type, "contact": contact, "text": "(demo)",
                            "retention_until": (t + timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        usage.append(_usage(ch, conv_id, msg_id, t, "channel", ch.channel_type, f"message.{direction}", 1, "message"))
                        if direction == "outbound":
                            outbound += 1
                            usage.append(_usage(ch, conv_id, msg_id, t, "platform", "flowsdone", "ai_message", 1, "message"))
                            tokens_in = random.randint(600, 2400)
                            usage.append(_usage(ch, conv_id, msg_id, t, "llm", "openai", MODEL, tokens_in, "input_token"))
                            usage.append(_usage(ch, conv_id, msg_id, t, "llm", "openai", MODEL, random.randint(40, 260), "output_token"))
                            usage.append(_usage(ch, conv_id, msg_id, t, "llm", "openai", MODEL, int(tokens_in * random.uniform(0, 0.6)), "cached_input_token"))
                        else:
                            inbound += 1
                    t += timedelta(seconds=random.randint(20, 240))  # the customer reads and types
                is_open = (now - t) < timedelta(hours=24)
                conversations.append({
                    "id": conv_id, "session_id": session, "tenant_id": ch.tenant_id, "project_id": ch.project_id,
                    "agent_id": ch.agent_id, "channel_type": ch.channel_type, "channel_connection_id": ch.connection_id,
                    "contact": contact, "status": "open" if is_open else "closed", "started_at": start,
                    "last_inbound_at": t, "last_message_at": t, "inbound_count": inbound, "outbound_count": outbound,
                    "closed_at": None if is_open else t + timedelta(hours=24),
                    "close_reason": None if is_open else random.choice(CLOSE_REASONS),
                })
    return conversations, messages, usage


def _usage(ch: Channel, conv_id: str, msg_id: str, at: datetime, kind: str, provider: str, sku: str,
           quantity: int, unit: str) -> Dict:
    """One usage_events row.

    Args:
        ch (Channel): Where it happened.
        conv_id (str): Conversation.
        msg_id (str): Message.
        at (datetime): When.
        kind (str): channel / platform / llm.
        provider (str): Provider label.
        sku (str): SKU (model, message.inbound…).
        quantity (int): Amount.
        unit (str): Unit.

    Returns:
        Dict: The row.
    """
    return {
        "event_id": str(uuid.uuid4()), "ts": ts(at), "tenant_id": ch.tenant_id, "project_id": ch.project_id,
        "conversation_id": conv_id, "message_id": msg_id, "channel_type": ch.channel_type,
        "trace_id": f"{SEED_TAG}{conv_id}", "kind": kind, "provider": provider, "sku": sku,
        "quantity": quantity, "unit": unit,
    }


async def main() -> None:
    """Parse arguments and seed (or clear) the demo data."""
    guard()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--clear", action="store_true", help="only remove previously seeded data")
    args = parser.parse_args()

    engine = create_async_engine(os.environ["DATABASE_URL_SQLALCHEMY"])
    ch_client = httpx.Client(
        base_url=os.environ.get("CLICKHOUSE_URL", "http://clickhouse:8123"),
        auth=(os.environ.get("CLICKHOUSE_APP_USER", "flowsdone_app"), os.environ["CLICKHOUSE_APP_PASSWORD"]),
        timeout=120,
    )
    db = os.environ.get("CLICKHOUSE_DATABASE", "flowsdone")

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM conversations WHERE session_id LIKE 'seed:%'"))
    # ALTER ... DELETE (the app user has ALTER DELETE, not the lightweight DELETE grant).
    clickhouse(ch_client, f"ALTER TABLE {db}.messages DELETE WHERE startsWith(session_id, 'seed:') SETTINGS mutations_sync = 1")
    clickhouse(ch_client, f"ALTER TABLE {db}.usage_events DELETE WHERE startsWith(trace_id, 'seed:') SETTINGS mutations_sync = 1")
    print("seed_analytics: datos de ejemplo anteriores borrados")
    if args.clear:
        return

    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT p.tenant_id, c.project_id, c.agent_id, c.id, c.channel_type
            FROM channel_connections c JOIN projects p ON p.id = c.project_id
            WHERE c.channel_type IN ('whatsapp_evolution', 'instagram', 'telegram', 'facebook', 'voice')
        """))).all()
    channels = [Channel(*(str(v) for v in row)) for row in rows]
    if not channels:
        sys.exit("seed_analytics: no hay canales (WhatsApp, Instagram, Telegram, Messenger o voz) a los que añadir tráfico")

    random.seed(42)
    conversations, messages, usage = build(channels, args.days)
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO conversations (id, session_id, tenant_id, project_id, agent_id, channel_type,
                channel_connection_id, contact, status, started_at, last_inbound_at, last_message_at,
                inbound_count, outbound_count, closed_at, close_reason)
            VALUES (:id, :session_id, :tenant_id, :project_id, :agent_id, :channel_type, :channel_connection_id,
                :contact, :status, :started_at, :last_inbound_at, :last_message_at, :inbound_count,
                :outbound_count, :closed_at, :close_reason)
        """), conversations)
    for start in range(0, len(messages), 20000):
        clickhouse(ch_client, f"INSERT INTO {db}.messages FORMAT JSONEachRow", messages[start:start + 20000])
    for start in range(0, len(usage), 20000):
        clickhouse(ch_client, f"INSERT INTO {db}.usage_events FORMAT JSONEachRow", usage[start:start + 20000])
    await engine.dispose()
    print(f"seed_analytics: {len(conversations)} conversaciones, {len(messages)} mensajes, "
          f"{len(usage)} eventos de consumo en {len(channels)} canales ({args.days} días)")


if __name__ == "__main__":
    asyncio.run(main())
