#!/usr/bin/env bash
# =============================================================================
# backup-postgres.sh — pg_dump comprimido de cada base (gatewaydb, langfusedb,
# langflowdb, evolutiondb, n8ndb), un archivo por base.
#
# Uso:
#   ./scripts/backup-postgres.sh
#
# Variables opcionales:
#   CONTAINER_PREFIX       prefijo del container_name (default: fd, como en .env)
#   BACKUP_DIR              destino de los dumps (default: ./backups/postgres)
#   BACKUP_RETENTION_DAYS   borra dumps más viejos que N días (default: 14)
#
# Pensado para cron, ej. diario a las 3am:
#   0 3 * * * cd /srv/Flowsdone_Ecosystem && ./scripts/backup-postgres.sh >> ./backups/postgres/backup.log 2>&1
#
# Restaurar una base:
#   gunzip -c backups/postgres/gatewaydb_20260828_030000.sql.gz | \
#     docker exec -i fd_postgres psql -U flowsdone_admin -d gatewaydb
# =============================================================================
set -euo pipefail

CONTAINER_PREFIX="${CONTAINER_PREFIX:-fd}"
CONTAINER="${CONTAINER_PREFIX}_postgres"
BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

log() { echo "[$(date +%H:%M:%S)] $*"; }

mkdir -p "$BACKUP_DIR"

if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" >/dev/null 2>&1; then
  log "✗ El contenedor '$CONTAINER' no está corriendo." >&2
  exit 1
fi

# POSTGRES_USER y POSTGRES_MULTIPLE_DATABASES los toma del propio entorno del
# contenedor, no hace falta parsear .env acá.
databases="$(docker exec "$CONTAINER" printenv POSTGRES_MULTIPLE_DATABASES)"
pg_user="$(docker exec "$CONTAINER" printenv POSTGRES_USER)"

failed=0
IFS=',' read -ra DB_LIST <<< "$databases"
for db in "${DB_LIST[@]}"; do
  db="$(echo "$db" | xargs)"
  [ -z "$db" ] && continue

  out_file="${BACKUP_DIR}/${db}_${TIMESTAMP}.sql.gz"
  log "Backup de '$db'..."
  # Conexión local por socket dentro del propio contenedor: no necesita password.
  if docker exec "$CONTAINER" pg_dump -U "$pg_user" -d "$db" | gzip > "$out_file"; then
    log "✓ ${out_file} ($(du -h "$out_file" | cut -f1))"
  else
    log "✗ Falló el backup de '$db'" >&2
    rm -f "$out_file"
    failed=1
  fi
done

log "Limpiando backups de más de ${BACKUP_RETENTION_DAYS} días en ${BACKUP_DIR}..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -delete

exit $failed
