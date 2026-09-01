#!/bin/sh
# Pensado para correr DENTRO del contenedor de opensearch-dashboards,
# vía `docker exec -i <container> sh -s < init-dashboards.sh` (ver
# ecosistems_up.sh / deploy.yml), con dashboards-export.ndjson ya
# copiado a /tmp con `docker cp` antes de invocarlo.
set -eu

DASHBOARDS_URL="http://localhost:5601"
AUTH="${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}"
NDJSON="/tmp/dashboards-export.ndjson"

echo "Importando saved objects (index pattern logs-*, dashboard Observabilidad de logs)..."
status=$(curl -s -o /tmp/os_import_response.json -w "%{http_code}" \
  -u "$AUTH" -H "osd-xsrf: osd-fetch" \
  -X POST "${DASHBOARDS_URL}/api/saved_objects/_import?overwrite=true" \
  -F "file=@${NDJSON};type=application/ndjson")

if [ "$status" != "200" ]; then
  echo "Fallo importando saved objects (HTTP $status):"
  cat /tmp/os_import_response.json
  exit 1
fi

if grep -q '"success":false' /tmp/os_import_response.json; then
  echo "La importación reportó errores:"
  cat /tmp/os_import_response.json
  exit 1
fi

echo "opensearch-dashboards-init: listo."
