#!/bin/sh
set -eu

OPENSEARCH_URL="https://opensearch:9200"
AUTH="${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}"
LEGACY_INDEX="ss4o_logs-default-namespace"

curl_json() {
  curl -k -s -o /tmp/os_response.json -w "%{http_code}" \
    -u "$AUTH" -H "Content-Type: application/json" "$@"
}

echo "Aplicando index template 'logs' para el patrón logs-*..."
status=$(curl_json -X PUT "${OPENSEARCH_URL}/_index_template/logs" -d @- <<'EOF'
{
  "index_patterns": ["logs-*"],
  "priority": 100,
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "dynamic_templates": [
        {
          "attributes_as_keyword": {
            "path_match": "attributes.*",
            "match_mapping_type": "string",
            "mapping": { "type": "keyword" }
          }
        },
        {
          "resource_as_keyword": {
            "path_match": "resource.*",
            "match_mapping_type": "string",
            "mapping": { "type": "keyword" }
          }
        }
      ],
      "properties": {
        "@timestamp": { "type": "date" },
        "observedTimestamp": { "type": "date" },
        "body": { "type": "text" },
        "severity": {
          "properties": {
            "number": { "type": "integer" },
            "text": { "type": "keyword" }
          }
        },
        "resource": {
          "properties": {
            "service": {
              "properties": {
                "name": { "type": "keyword" }
              }
            },
            "source": { "type": "keyword" }
          }
        },
        "attributes": {
          "properties": {
            "container_id": { "type": "keyword" }
          }
        }
      }
    }
  }
}
EOF
)
if [ "$status" != "200" ]; then
  echo "Fallo creando el index template (HTTP $status):"
  cat /tmp/os_response.json
  exit 1
fi
echo "Index template 'logs' aplicado (HTTP $status)."

echo "Eliminando índice legacy '${LEGACY_INDEX}' (mezclaba todos los servicios)..."
status=$(curl_json -X DELETE "${OPENSEARCH_URL}/${LEGACY_INDEX}")
if [ "$status" = "200" ] || [ "$status" = "404" ]; then
  echo "OK (HTTP $status)."
else
  echo "Fallo eliminando el índice legacy (HTTP $status):"
  cat /tmp/os_response.json
  exit 1
fi

echo "opensearch-init: listo."
