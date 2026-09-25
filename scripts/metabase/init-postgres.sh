#!/bin/sh
# Prepara Postgres para Metabase (idempotente). Se ejecuta DENTRO del
# contenedor de Postgres, después de las migraciones de Alembic:
#   docker exec -i "$PG_CONTAINER" sh -s < scripts/metabase/init-postgres.sh
#
# - Base "metabasedb": la base interna de Metabase (sus dashboards, preguntas
#   y usuarios). init-db.sh solo crea bases al inicializar un volumen nuevo,
#   por eso se crea también aquí.
# - Rol "metabase_reader": con el que Metabase lee gatewaydb. SOLO puede leer
#   el esquema analytics (vistas sin datos sensibles, migración 0013); nada
#   de public. Su contraseña sale de METABASE_READER_PASSWORD (variable del
#   contenedor, ver docker-compose.yml).
set -eu

DB="${METABASE_DB:-metabasedb}"
READER="metabase_reader"
: "${METABASE_READER_PASSWORD:?Falta METABASE_READER_PASSWORD en el contenedor de postgres}"

psql_admin() {
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" "$@"
}

psql_admin --dbname postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB}'" | grep -q 1 \
  || psql_admin --dbname postgres -c "CREATE DATABASE \"${DB}\""

psql_admin --dbname postgres -v pw="$METABASE_READER_PASSWORD" <<SQL
SELECT format('CREATE ROLE ${READER} LOGIN PASSWORD %L', :'pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${READER}')\gexec
SELECT format('ALTER ROLE ${READER} WITH LOGIN PASSWORD %L', :'pw')\gexec
SQL

psql_admin --dbname gatewaydb <<SQL
REVOKE ALL ON DATABASE gatewaydb FROM ${READER};
GRANT CONNECT ON DATABASE gatewaydb TO ${READER};
REVOKE ALL ON SCHEMA public FROM ${READER};
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ${READER};
GRANT USAGE ON SCHEMA analytics TO ${READER};
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ${READER};
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO ${READER};
SQL

echo "metabase: base ${DB} y rol ${READER} listos"
