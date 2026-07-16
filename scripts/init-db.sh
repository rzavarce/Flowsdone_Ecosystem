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

  if echo "$POSTGRES_MULTIPLE_DATABASES" | grep -qw "gatewaydb"; then
    echo "🛠️ Ensuring workflow_executions table exists in gatewaydb"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname gatewaydb <<-EOSQL
      CREATE TABLE IF NOT EXISTS workflow_executions (
        message_id text PRIMARY KEY,
        workflow_id text NOT NULL,
        status text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
      );
EOSQL
    echo "✅ workflow_executions table ensured"
  fi
fi