#!/bin/sh
# Crea (idempotente) la base "flowsdone" y sus tablas en ClickHouse.
# Se ejecuta DENTRO del contenedor de ClickHouse, con su usuario admin:
#   docker exec -i "$CH_CONTAINER" sh -s < scripts/clickhouse/init-clickhouse.sh
# El deploy lo corre antes de levantar kafka_conversations_worker.
#
# Cambios de esquema: solo sentencias idempotentes (IF NOT EXISTS), nunca
# DROP. Una columna nueva = ALTER TABLE ... ADD COLUMN IF NOT EXISTS al final.
set -eu

DB="${CLICKHOUSE_DATABASE:-flowsdone}"

ch() {
  clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --multiquery --query "$1"
}

ch "CREATE DATABASE IF NOT EXISTS ${DB}"

# Un mensaje por fila. ReplacingMergeTree + message_id en la clave: un evento
# re-entregado por Kafka colapsa sobre la misma fila (consultar con FINAL si
# hace falta exactitud antes del merge). Cada fila se borra en su propio
# retention_until (hoy ~6 meses; la retención ampliada por tenant solo cambia
# ese valor al insertar).
ch "
CREATE TABLE IF NOT EXISTS ${DB}.messages
(
    message_id            UUID,
    ts                    DateTime64(3, 'UTC'),
    tenant_id             UUID,
    project_id            UUID,
    agent_id              UUID,
    conversation_id       UUID,
    session_id            String,
    channel_type          LowCardinality(String),
    channel_connection_id UUID,
    direction             Enum8('inbound' = 1, 'outbound' = 2),
    sender_type           LowCardinality(String),
    app                   LowCardinality(String),
    contact               String,
    text                  String,
    billable              Bool DEFAULT true,
    retention_until       DateTime('UTC'),
    inserted_at           DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, conversation_id, ts, message_id)
TTL retention_until DELETE
"

# Consumo medido: solo CANTIDADES (mensajes por canal, tokens de LLM, mensajes
# procesados por la plataforma). El coste se calcula al leer, con el catálogo
# versionado de Postgres (cost_rates), así una tarifa nueva o corregida aplica
# bien también a lo ya medido; el cierre de mes congela los importes en
# usage_statements. cost_micros/price_micros quedan reservados (0).
# Sin TTL: respalda la facturación y se conserva años. event_id determinista
# (uuid5 del origen) -> reprocesar no duplica.
ch "
CREATE TABLE IF NOT EXISTS ${DB}.usage_events
(
    event_id        UUID,
    ts              DateTime64(3, 'UTC'),
    tenant_id       UUID,
    project_id      UUID,
    conversation_id Nullable(UUID),
    message_id      Nullable(UUID),
    channel_type    LowCardinality(String) DEFAULT '',
    trace_id        String DEFAULT '',
    kind            LowCardinality(String),
    provider        LowCardinality(String),
    sku             LowCardinality(String),
    quantity        Decimal(20, 6),
    unit            LowCardinality(String),
    cost_micros     Int64 DEFAULT 0,
    price_micros    Int64 DEFAULT 0,
    currency        LowCardinality(String) DEFAULT 'EUR',
    price_version   String DEFAULT '',
    inserted_at     DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(inserted_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, ts, event_id)
"

echo "clickhouse: base ${DB} lista"
