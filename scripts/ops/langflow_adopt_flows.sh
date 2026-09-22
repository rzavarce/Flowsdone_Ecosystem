#!/usr/bin/env bash
# Pasa los flujos de los agentes del gateway al usuario y a la carpeta de su tenant en
# Langflow, para que al abrir un tenant en Agentes se vean sus agentes.
#
# Por qué: hasta ahora todos los flujos eran del usuario `langflow`. El editor embebido
# abre Langflow como el usuario del tenant (uno por tenant, una carpeta por proyecto) y
# ese usuario solo ve lo suyo. Langflow no tiene API para cambiar el propietario de un
# flujo, así que se hace con UPDATE sobre su tabla `flow` (user_id y folder_id).
#
# Requisito: haber abierto cada tenant UNA vez en Agentes (eso crea su usuario y las
# carpetas). Los agentes de tenants aún sin abrir se listan como PENDIENTES.
#
# El gateway sigue ejecutando los agentes con la API key del superusuario, que puede
# leer y ejecutar flujos de otros usuarios; se comprueba con langflow_check_agent_flows.sh.
#
# Uso (raíz del repo):
#   scripts/ops/langflow_adopt_flows.sh [prod|dev]            # simulación: no cambia nada
#   scripts/ops/langflow_adopt_flows.sh [prod|dev] --apply    # aplica los cambios
# Idempotente. Solo toca los flujos de agentes registrados en el gateway.
set -euo pipefail

PROFILE="${1:-prod}"
APPLY="${2:-}"
cd "$(dirname "$0")/../.."
UUID_RE='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'

ROWS="$(docker compose --profile "$PROFILE" exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d gatewaydb -At -F "|" -c "
     select a.langflow_flow_id, la.langflow_user_id, lf.folder_id, t.slug, a.name
     from agents a
     join projects p on p.id = a.project_id
     join tenants t on t.id = p.tenant_id
     left join langflow_accounts la on la.tenant_id = t.id
     left join langflow_folders lf on lf.project_id = p.id
     order by t.slug, a.name"')"

[[ -n "$ROWS" ]] || { echo "No hay agentes en el gateway."; exit 0; }

SQL="BEGIN;"$'\n'
pending=0
planned=0
while IFS='|' read -r flow user folder slug name; do
  if [[ -z "$user" || -z "$folder" ]]; then
    echo "  PENDIENTE  $slug / $name: abre el tenant '$slug' en Agentes una vez y vuelve a ejecutar"
    pending=$((pending + 1))
    continue
  fi
  if ! [[ "$flow" =~ $UUID_RE && "$user" =~ $UUID_RE && "$folder" =~ $UUID_RE ]]; then
    echo "  OMITIDO    $slug / $name: identificadores con formato inesperado (flujo '$flow')"
    continue
  fi
  echo "  ADOPTAR    (si aún no lo está) $slug / $name  [flujo $flow -> usuario del tenant, carpeta del proyecto]"
  SQL+="UPDATE flow SET user_id = '$user', folder_id = '$folder' WHERE id = '$flow' AND (user_id IS DISTINCT FROM '$user' OR folder_id IS DISTINCT FROM '$folder');"$'\n'
  planned=$((planned + 1))
done <<< "$ROWS"
SQL+="COMMIT;"

echo "Agentes a adoptar: $planned; pendientes: $pending."
if [[ "$APPLY" != "--apply" ]]; then
  echo "Simulación: no se cambió nada. Añade --apply para ejecutar."
  exit 0
fi
[[ "$planned" -gt 0 ]] || { echo "Nada que aplicar."; exit 0; }

printf '%s\n' "$SQL" | docker compose --profile "$PROFILE" exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d langflowdb -v ON_ERROR_STOP=1 -q -X' | sed 's/^/  /'
echo "Hecho. Comprueba con: scripts/ops/langflow_check_agent_flows.sh $PROFILE"
