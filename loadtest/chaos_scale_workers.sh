#!/usr/bin/env bash
# Escenario 4 — Escalado horizontal en vivo.
#
# Corré esto EN PARALELO a un run de locust (otra terminal), idealmente
# durante la etapa de mayor carga (última stage de GradualRampShape en
# locustfile.py). Escala kafka_inbound_worker a REPLICAS réplicas, espera, y
# vuelve a 1 — el mismo comando que documenta el README (sección 9,
# "Particiones de Kafka por canal"). Con KAFKA_TOPIC_PARTITIONS=6 por
# defecto, hasta 6 réplicas pueden repartirse las particiones sin tocar
# código.
#
# Elige servidor automáticamente:
#   - VPS_HOST seteado  -> corre los comandos por SSH contra el VPS
#   - VPS_HOST vacío    -> corre docker compose directo, local (default)
#
# Uso (local, default):
#   REPLICAS=3 ./chaos_scale_workers.sh
# Uso (VPS):
#   source .env.vps && REPLICAS=3 ./chaos_scale_workers.sh

set -euo pipefail

VPS_HOST="${VPS_HOST:-}"
VPS_COMPOSE_DIR="${VPS_COMPOSE_DIR:-..}"
REPLICAS="${REPLICAS:-3}"
HOLD_SECONDS="${HOLD_SECONDS:-180}"

run() {
    if [ -n "$VPS_HOST" ]; then
        ssh "$VPS_HOST" "cd $VPS_COMPOSE_DIR && $1"
    else
        (cd "$VPS_COMPOSE_DIR" && eval "$1")
    fi
}

TARGET_DESC="${VPS_HOST:-local ($VPS_COMPOSE_DIR)}"
echo "[$(date -Iseconds)] Escalando kafka_inbound_worker a $REPLICAS réplicas en $TARGET_DESC ..."
run "docker compose up -d --scale kafka_inbound_worker=$REPLICAS"
echo "[$(date -Iseconds)] Escalado. Manteniendo $REPLICAS réplicas por ${HOLD_SECONDS}s — mirá el throughput/latencia subir en el reporte de locust."

sleep "$HOLD_SECONDS"

echo "[$(date -Iseconds)] Volviendo a 1 réplica ..."
run "docker compose up -d --scale kafka_inbound_worker=1"
echo "[$(date -Iseconds)] Listo. Comparar en el reporte de locust: throughput/latencia con $REPLICAS réplicas vs. con 1."
