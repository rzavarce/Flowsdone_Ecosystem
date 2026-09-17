#!/usr/bin/env bash
# Escenario 3 — Recuperación ante fallos.
#
# Corré esto EN PARALELO a un run de locust (otra terminal), contra el mismo
# servidor. Para kafka_inbound_worker durante DOWNTIME_SECONDS y lo vuelve a
# levantar. Como el webhook solo publica en Kafka y responde 200 de
# inmediato (ver README.md), el gateway debería seguir aceptando mensajes
# sin errores mientras el worker está caído — quedan en la cola y
# kafka_inbound_worker los procesa al volver. Compará los timestamps de este
# script contra el reporte de locust para confirmar que no hubo errores 5xx
# durante la ventana de caída, solo latencia de procesamiento acumulada.
#
# Elige servidor automáticamente:
#   - VPS_HOST seteado  -> corre los comandos por SSH contra el VPS
#   - VPS_HOST vacío    -> corre docker compose directo, local (default)
#
# Uso (local, default):
#   ./chaos_worker_restart.sh
# Uso (VPS):
#   source .env.vps && ./chaos_worker_restart.sh

set -euo pipefail

VPS_HOST="${VPS_HOST:-}"
VPS_COMPOSE_DIR="${VPS_COMPOSE_DIR:-..}"
DOWNTIME_SECONDS="${DOWNTIME_SECONDS:-60}"

run() {
    if [ -n "$VPS_HOST" ]; then
        ssh "$VPS_HOST" "cd $VPS_COMPOSE_DIR && $1"
    else
        (cd "$VPS_COMPOSE_DIR" && eval "$1")
    fi
}

TARGET_DESC="${VPS_HOST:-local ($VPS_COMPOSE_DIR)}"
echo "[$(date -Iseconds)] Deteniendo kafka_inbound_worker en $TARGET_DESC ..."
run "docker compose stop kafka_inbound_worker"
echo "[$(date -Iseconds)] Worker detenido. Esperando ${DOWNTIME_SECONDS}s con el worker caído (el gateway debería seguir respondiendo 200)."

sleep "$DOWNTIME_SECONDS"

echo "[$(date -Iseconds)] Levantando kafka_inbound_worker de nuevo ..."
run "docker compose start kafka_inbound_worker"
echo "[$(date -Iseconds)] Worker recuperado. Revisá el backlog de Kafka drenándose en los logs:"
if [ -n "$VPS_HOST" ]; then
    echo "  ssh $VPS_HOST 'cd $VPS_COMPOSE_DIR && docker compose logs -f --tail=50 kafka_inbound_worker'"
else
    echo "  (cd $VPS_COMPOSE_DIR && docker compose logs -f --tail=50 kafka_inbound_worker)"
fi
