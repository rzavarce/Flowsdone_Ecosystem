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
#   --reset-postgres       borra ./volumes/postgres_data antes de arrancar
#                           (solo perfil dev; rechaza correr con prod). Pedí
#                           un backup fresco antes con scripts/backup-postgres.sh
#                           si te importa lo que hay ahí.
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
RESET_POSTGRES=false

for arg in "$@"; do
  case "$arg" in
    --skip-observability) SKIP_OBSERVABILITY=true ;;
    --skip-ui)            SKIP_UI=true ;;
    --only-infra)         ONLY_INFRA=true ;;
    --reset-postgres)     RESET_POSTGRES=true ;;
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
if $RESET_POSTGRES; then
  [[ "$PROFILE" == "prod" ]] && \
    error "--reset-postgres no se puede usar con el perfil 'prod' (borraría datos reales). Si hace falta de verdad, hacelo a mano, con un backup fresco antes."
  warn "--reset-postgres: borrando ./volumes/postgres_data..."
  compose stop postgres >/dev/null 2>&1 || true
  compose rm -f postgres >/dev/null 2>&1 || true
  # postgres_data queda con permisos 700 del uid interno de postgres, así que
  # un "rm -rf ./volumes/postgres_data/*" del usuario sin privilegios no
  # borraría nada (el glob se expande vacío antes de que sudo entre en
  # juego). Hay que apuntar al directorio en sí, no a su contenido.
  sudo rm -rf ./volumes/postgres_data
  success "./volumes/postgres_data vaciado."
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
log "Creando bucket MinIO '${MINIO_BUCKET}'…"
minio_container=$(resolve_container_id minio || true)
if [[ -z "$minio_container" ]]; then
  error "No se encontró el contenedor de minio para crear el bucket."
fi

# mc ya viene incluido en la imagen de minio (se usa en su healthcheck),
# así que ejecutamos dentro del propio contenedor en vez de levantar uno
# aparte — evita depender de red/pull de minio/mc y de tener que parsear
# el texto de salida para saber si ya existía.
alias_ok=false
for attempt in $(seq 1 12); do
  if docker exec "$minio_container" mc alias set local "http://localhost:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1; then
    alias_ok=true
    break
  fi
  sleep 5
done
$alias_ok || error "No se pudo autenticar con MinIO tras varios intentos (¿el servicio está healthy?)."

bucket_ok=false
for attempt in $(seq 1 12); do
  if docker exec "$minio_container" mc mb --ignore-existing "local/${MINIO_BUCKET}" >/dev/null 2>&1; then
    bucket_ok=true
    break
  fi
  sleep 5
done
if $bucket_ok; then
  success "Bucket '${MINIO_BUCKET}' listo."
else
  error "No se pudo crear el bucket '${MINIO_BUCKET}' tras varios intentos. Sin este bucket, Langfuse falla en silencio (500) al recibir trazas."
fi

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

    # Index template de logs-* (mapping ss4o) + limpieza del índice legacy.
    # Tiene que correr ANTES de arrancar otel-collector (más abajo): si
    # otel-collector escribe el primer log antes de que exista el template,
    # el índice queda creado con mapping dinámico (el problema original que
    # este template soluciona) y ya no hay forma de corregirlo sin borrarlo.
    log "Aplicando index template de OpenSearch…"
    docker exec -i "$opensearch_container" sh -s < ./scripts/opensearch/init-opensearch.sh \
      && success "Index template de OpenSearch aplicado." \
      || warn "No se pudo aplicar el index template de OpenSearch; se continúa."
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

  if ! $SKIP_OBSERVABILITY; then
    wait_healthy opensearch-dashboards 120
    dashboards_container=$(resolve_container_id opensearch-dashboards || true)
    if [[ -n "$dashboards_container" ]]; then
      log "Importando index pattern + dashboard de OpenSearch…"
      docker cp ./scripts/opensearch/dashboards-export.ndjson \
        "${dashboards_container}:/tmp/dashboards-export.ndjson"
      docker exec -i "$dashboards_container" sh -s < ./scripts/opensearch/init-dashboards.sh \
        && success "Dashboard de OpenSearch importado." \
        || warn "No se pudo importar el dashboard de OpenSearch; se continúa."
      # Sin cleanup del ndjson en /tmp: el contenedor corre como un usuario
      # no-root, docker cp lo crea como root, y con el sticky bit de /tmp
      # ese usuario no puede borrarlo ("Operation not permitted") - con
      # set -e eso mataba el script entero. /tmp es la capa efímera del
      # contenedor, se limpia solo en el próximo recreate.
    fi
  fi
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
