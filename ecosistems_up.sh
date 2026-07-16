#!/usr/bin/env bash
# =============================================================================
# ecosistems_up.sh — Arranque por fases del stack Flowsdone
#
# Uso:
#   ./ecosistems_up.sh              # arranca en modo dev (por defecto)
#   ./ecosistems_up.sh prod         # arranca en modo prod (incluye Traefik)
#
# Flags opcionales:
#   --skip-observability   omite OpenSearch + OTEL Collector
#   --skip-ui              omite todos los paneles web
#   --only-infra           arranca solo la infraestructura base
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()     { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
success() { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"; }
warn()    { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC}  $*"; }
error()   { echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*"; exit 1; }
phase()   { echo -e "\n${BOLD}${CYAN}━━━ $* ━━━${NC}\n"; }

PROFILE="dev"
SKIP_OBSERVABILITY=false
SKIP_UI=false
ONLY_INFRA=false

for arg in "$@"; do
  case "$arg" in
    --skip-observability) SKIP_OBSERVABILITY=true ;;
    --skip-ui)            SKIP_UI=true ;;
    --only-infra)         ONLY_INFRA=true ;;
    dev|prod)
      PROFILE="$arg"
      ;;
    *)
      error "Argumento no reconocido: '$arg'"
      ;;
  esac
done

[[ "$PROFILE" != "dev" && "$PROFILE" != "prod" ]] && \
  error "Perfil inválido: '$PROFILE'. Usa 'dev' o 'prod'."

load_env_file() {
  local line key value
  [[ -f ".env" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    export "$key=$value"
  done < ".env"
}

load_env_file

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-fd-ecosystem}"
compose() {
  docker compose --profile "$PROFILE" "$@"
}

is_port_free() {
  local port="$1"
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(:${port})$"; then
    return 1
  fi
  return 0
}

find_available_port() {
  local preferred="$1"
  local port="$preferred"
  while ! is_port_free "$port"; do
    port=$((port + 1))
  done
  echo "$port"
}

resolve_container_id() {
  local service="$1"
  local cid=""

  cid=$(compose ps -q "$service" 2>/dev/null | head -1 || true)
  [[ -n "$cid" ]] && { echo "$cid"; return 0; }

  cid=$(docker ps -q \
    --filter "label=com.docker.compose.service=$service" \
    --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" \
    2>/dev/null | head -1 || true)
  [[ -n "$cid" ]] && { echo "$cid"; return 0; }

  return 1
}

wait_healthy() {
  local service="$1"
  local timeout="${2:-180}"
  local container=""
  local elapsed=0
  local status=""

  while [[ -z "$container" ]] && (( elapsed < 20 )); do
    container=$(resolve_container_id "$service" || true)
    if [[ -z "$container" ]]; then
      sleep 4
      elapsed=$((elapsed + 4))
    fi
  done

  if [[ -z "$container" ]]; then
    warn "No se encontró el contenedor de '$service' tras ${elapsed}s, se continúa."
    return 0
  fi

  log "Esperando a que '$service' esté healthy (máx. ${timeout}s)…"
  elapsed=0

  while true; do
    status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no healthcheck{{end}}' "$container" 2>/dev/null || echo "unknown")

    case "$status" in
      healthy)
        success "'$service' está healthy."
        return 0
        ;;
      unhealthy)
        if (( elapsed < 60 )); then
          warn "'$service' unhealthy a los ${elapsed}s — reintentando…"
        else
          echo ""
          warn "Health log de '$service':"
          docker inspect --format='{{range .State.Health.Log}}  [exit={{.ExitCode}}] {{.Output}}{{end}}' "$container" 2>/dev/null | tail -5 || true
          error "'$service' quedó unhealthy."
        fi
        ;;
      "no healthcheck")
        warn "'$service' no tiene healthcheck definido, continuando…"
        return 0
        ;;
    esac

    if (( elapsed >= timeout )); then
      echo ""
      error "Timeout esperando '$service' después de ${timeout}s (estado: $status)"
    fi

    sleep 5
    elapsed=$((elapsed + 5))
    echo -ne "  ${YELLOW}…${NC} ${elapsed}s / ${timeout}s\r"
  done
}

phase "Verificaciones previas"
command -v docker >/dev/null 2>&1 || error "Docker no encontrado."
docker info >/dev/null 2>&1 || error "El daemon de Docker no está corriendo."
[[ -f ".env" ]] || error "No se encontró .env en el directorio actual."

log "Perfil activo    : ${BOLD}$PROFILE${NC}"
log "Proyecto Compose : ${BOLD}$COMPOSE_PROJECT_NAME${NC}"
$SKIP_OBSERVABILITY && warn "--skip-observability: se omiten OpenSearch y OTEL Collector."
$SKIP_UI            && warn "--skip-ui: se omiten los paneles web."
$ONLY_INFRA         && warn "--only-infra: se arranca solo la infraestructura base."

phase "Fase 1a — Fundación (postgres + redis)"
if [[ -d "./volumes/postgres_data" ]] && find "./volumes/postgres_data" -mindepth 1 -maxdepth 1 | grep -q .; then
  warn "Se detectó estado previo en ./volumes/postgres_data; se limpiará para reiniciar Postgres limpio."
  find "./volumes/postgres_data" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi
compose up -d --force-recreate --remove-orphans --no-deps postgres redis
wait_healthy postgres 300
wait_healthy redis 120
success "Postgres y Redis están listos."

phase "Fase 1b — Infraestructura pesada"
for svc in rabbitmq kafka minio weaviate clickhouse; do
  if [[ "$svc" == "rabbitmq" ]]; then
    local_rabbitmq_mgmt_port="${RABBITMQ_MGMT_PORT:-15672}"
    if ! is_port_free "$local_rabbitmq_mgmt_port"; then
      resolved_port=$(find_available_port "$local_rabbitmq_mgmt_port")
      warn "El puerto $local_rabbitmq_mgmt_port está ocupado; se usará $resolved_port para RabbitMQ Management."
      export RABBITMQ_MGMT_PORT="$resolved_port"
    fi
  fi

  log "Arrancando $svc…"
  compose up -d --remove-orphans --no-deps "$svc"
  wait_healthy "$svc" 300
  echo
 done
success "Infraestructura base completa."

phase "Fase 2 — MinIO + observabilidad"
MINIO_INTERNAL_PORT="${MINIO_PORT:-${MINIO_API_PORT:-9000}}"
log "Creando bucket MinIO '${MINIO_BUCKET}'…"
MC_VOL="mc_config_$$"
docker volume create "$MC_VOL" >/dev/null
minio_container=$(resolve_container_id minio || true)
if [[ -z "$minio_container" ]]; then
  error "No se encontró el contenedor de minio para crear el bucket."
fi
network_name=$(docker inspect "$minio_container" --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' 2>/dev/null | head -1 || true)
if [[ -z "$network_name" ]]; then
  error "No se pudo resolver la red de minio."
fi

for attempt in $(seq 1 12); do
  if docker run --rm \
    --network "$network_name" \
    -v "${MC_VOL}:/root/.mc" \
    minio/mc alias set local "http://minio:${MINIO_INTERNAL_PORT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" --quiet >/dev/null 2>&1; then
    break
  fi
  sleep 5
 done

BUCKET_OUTPUT=""
for attempt in $(seq 1 12); do
  BUCKET_OUTPUT=$(docker run --rm \
    --network "$network_name" \
    -v "${MC_VOL}:/root/.mc" \
    minio/mc mb "local/${MINIO_BUCKET}" 2>&1) && break || true
  sleep 5
 done
if echo "$BUCKET_OUTPUT" | grep -qiE "already (exists|owned|your bucket)"; then
  success "Bucket '${MINIO_BUCKET}' ya existe — sin cambios."
elif echo "$BUCKET_OUTPUT" | grep -qiE "created|success"; then
  success "Bucket '${MINIO_BUCKET}' creado."
else
  warn "No se pudo validar la creación del bucket: $BUCKET_OUTPUT"
fi

docker volume rm "$MC_VOL" >/dev/null 2>&1 || true

$ONLY_INFRA && { success "Modo --only-infra: finalizado."; exit 0; }

if ! $SKIP_OBSERVABILITY; then
  log "Arrancando OpenSearch…"
  compose up -d --remove-orphans --no-deps opensearch
  sleep 30
  opensearch_container=$(resolve_container_id opensearch || true)
  if [[ -n "$opensearch_container" ]]; then
    docker exec "$opensearch_container" curl -sf --max-time 5 -ku "admin:${OPENSEARCH_PASSWORD}" https://localhost:9200/_cluster/health 2>/dev/null | grep -q status \
      && success "OpenSearch responde." \
      || warn "OpenSearch aún no responde; se continúa."
  fi
fi

phase "Fase 3 — Plataformas (langfuse, n8n, evolution, langflow)"
compose up -d --remove-orphans --no-deps langfuse-web langflow n8n evolution
sleep 20
compose up -d --remove-orphans --no-deps langfuse-worker
sleep 20
success "Plataformas arrancadas."

if ! $SKIP_OBSERVABILITY; then
  log "Arrancando OTEL Collector…"
  compose up -d --remove-orphans --no-deps otel-collector
fi

phase "Fase 4 — Gateway y workers"
compose up -d --remove-orphans --no-deps api kafka_inbound_worker kafka_outbound_worker rabbitmq_inbound_worker rabbitmq_outbound_worker
sleep 15
success "Gateway y workers arrancados."

phase "Fase 5 — Paneles web"
if ! $SKIP_UI; then
  UI_SERVICES=(redis-insight rabbitmq-scout weaviate-gui)
  $SKIP_OBSERVABILITY || UI_SERVICES+=(opensearch-dashboards)
  log "Arrancando paneles web: ${UI_SERVICES[*]}"
  compose up -d --remove-orphans --no-deps "${UI_SERVICES[@]}"
  success "Paneles web arrancados."
fi

if [[ "$PROFILE" == "prod" ]]; then
  phase "Fase 6 — Traefik"
  compose up -d --remove-orphans --no-deps traefik
  success "Traefik arrancado."
fi

phase "Stack listo"
echo -e "${BOLD}Estado de los contenedores:${NC}"
compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""
success "Arranque completado en perfil '${PROFILE}'."
echo ""
echo -e "  Apagar todo:             ${CYAN}docker compose --profile $PROFILE down${NC}"
echo -e "  Ver logs en tiempo real: ${CYAN}docker compose --profile $PROFILE logs -f${NC}"
echo -e "  Estado detallado:        ${CYAN}docker compose --profile $PROFILE ps${NC}"
