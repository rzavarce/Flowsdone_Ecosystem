#!/usr/bin/env bash
# Comprueba que el flujo de cada agente del gateway existe en Langflow y que la API key
# del gateway puede leerlo. Úsalo ANTES de cerrar el auto-login de Langflow y después.
#
# Por qué: con LANGFLOW_AUTO_LOGIN=true Langflow acepta peticiones sin clave y muestra
# flujos sin propietario; con el login real, la API key solo ve lo que le pertenece. Un
# agente cuyo flujo no exista o sea de otro usuario dejaría de responder.
#
# Uso (raíz del repo):  scripts/ops/langflow_check_agent_flows.sh [prod|dev]
# Sale con código 1 si algún agente con canales ACTIVOS tiene el flujo inaccesible.
# No imprime la API key. Solo nombres de agentes e IDs de flujo.
set -euo pipefail

PROFILE="${1:-prod}"
cd "$(dirname "$0")/../.."

ROWS="$(docker compose --profile "$PROFILE" exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d gatewaydb -At -F "|" -c "
     select a.name, a.langflow_flow_id,
            (select count(*) from channel_connections c where c.agent_id = a.id and c.status = '"'"'active'"'"')
     from agents a order by 3 desc, 1"')"

[[ -n "$ROWS" ]] || { echo "No hay agentes en el gateway."; exit 0; }

PYCODE=$(cat <<'PY'
import sys

import httpx

from app.core.config import settings as s

headers = {"x-api-key": s.LANGFLOW_API_KEY or ""}
me = httpx.get(s.LANGFLOW_BASE_URL + "/api/v1/users/whoami", headers=headers, timeout=30)
if me.status_code != 200:
    print(f"API key del gateway: RECHAZADA (HTTP {me.status_code})")
    sys.exit(2)
print("API key del gateway: válida (usuario " + str(me.json().get("username")) + ")")

bad = 0
for line in sys.stdin.read().splitlines():
    name, flow, channels = line.split("|")
    active = int(channels)
    r = httpx.get(f"{s.LANGFLOW_BASE_URL}/api/v1/flows/{flow}", headers=headers, timeout=30)
    if r.status_code == 200:
        state = "OK"
    elif active > 0:
        bad += 1
        state = "SIN ACCESO/INEXISTENTE  <-- TIENE CANALES ACTIVOS"
    else:
        state = "SIN ACCESO/INEXISTENTE  (sin canales activos)"
    print(f"  {state:50s} {name}  [flujo {flow[:36]}, {active} canal(es) activo(s)]")

if bad:
    print(f"RESULTADO: {bad} agente(s) con canales activos y flujo inaccesible")
    sys.exit(1)
print("RESULTADO: todos los agentes con canales activos tienen flujo accesible")
PY
)

printf '%s\n' "$ROWS" | docker compose --profile "$PROFILE" exec -T api python -c "$PYCODE"
