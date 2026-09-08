#!/bin/bash
set -e
set -u

function create_database() {
  local database=$1
  echo "🗄️ Creating database '$database'..."

  psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname postgres <<-EOSQL
    SELECT 'CREATE DATABASE $database'
    WHERE NOT EXISTS (
      SELECT FROM pg_database WHERE datname = '$database'
    )\gexec
EOSQL
}

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
  echo "⚙️ Multiple databases requested: $POSTGRES_MULTIPLE_DATABASES"

  for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ',' ' '); do
    create_database "$db"
  done

  echo "✅ All databases created"

  # El esquema de gatewaydb (workflow_executions, tenants, projects, agents,
  # workflows, channel_connections) lo gestiona Alembic — ver el servicio
  # `migrate` en docker-compose.yml y api_gateway/migrations/.
fi