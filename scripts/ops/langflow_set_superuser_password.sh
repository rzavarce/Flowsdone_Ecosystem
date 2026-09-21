#!/usr/bin/env bash
# Cambia la contraseña del superusuario de Langflow que YA existe.
#
# Por qué existe: al activar LANGFLOW_AUTO_LOGIN=false, Langflow crea el superusuario
# con LANGFLOW_SUPERUSER_PASSWORD SOLO si no existe. El de un Langflow ya en uso
# conserva su contraseña anterior (por defecto `langflow`), que es pública. Validado
# con un Langflow 1.4.0 temporal: sin este paso, `langflow`/`langflow` sigue entrando
# y la variable no sirve.
#
# Uso (desde la raíz del repo, con el Langflow actual corriendo):
#   1) Poner LANGFLOW_SUPERUSER_PASSWORD=<contraseña fuerte> en .env
#   2) scripts/ops/langflow_set_superuser_password.sh [prod|dev]      (default: prod)
#   3) Desplegar / recrear Langflow con la configuración nueva (AUTO_LOGIN=false)
#
# La contraseña se lee de .env y viaja por stdin: no aparece en la línea de comandos,
# ni en el historial, ni en la salida. La API key del gateway no cambia (sigue válida).
set -euo pipefail

PROFILE="${1:-prod}"
cd "$(dirname "$0")/../.."
[[ -f .env ]] || { echo "error: no existe .env en $(pwd)" >&2; exit 1; }

PASSWORD="$(grep -E '^LANGFLOW_SUPERUSER_PASSWORD=' .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
USERNAME="$(grep -E '^LANGFLOW_SUPERUSER=' .env | tail -1 | cut -d= -f2- | tr -d "\"' " || true)"
USERNAME="${USERNAME:-langflow}"

[[ -n "$PASSWORD" ]] || { echo "error: LANGFLOW_SUPERUSER_PASSWORD está vacía en .env" >&2; exit 1; }
[[ "${#PASSWORD}" -ge 16 ]] || { echo "error: la contraseña debe tener al menos 16 caracteres" >&2; exit 1; }
[[ "$PASSWORD" != "langflow" ]] || { echo "error: no puede ser 'langflow' (es la de por defecto)" >&2; exit 1; }

PYCODE=$(cat <<'PY'
import json, os, sys, urllib.error, urllib.parse, urllib.request

BASE = "http://127.0.0.1:7860"
USER = os.environ["LF_USER"]
NEW = sys.stdin.read().rstrip("\n")


def call(method, path, body=None, form=None, token=None):
    headers, data = {}, None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def token_for(password):
    status, j = call("POST", "/api/v1/login", form={"username": USER, "password": password})
    return j.get("access_token") if status == 200 and j else None


# Ya está aplicada: entra con la nueva y no hay nada que hacer.
if token_for(NEW):
    print("La contraseña nueva ya está aplicada; no hay nada que cambiar.")
    sys.exit(0)

# Camino 1: auto-login activo (el estado actual de un Langflow sin configurar).
status, j = call("GET", "/api/v1/auto_login")
token = j.get("access_token") if status == 200 and j else None
how = "auto-login"
# Camino 2: ya se cerró el auto-login pero el usuario sigue con la contraseña por defecto.
if not token:
    token, how = token_for("langflow"), "contraseña por defecto"
if not token:
    print("error: no se pudo autenticar con el auto-login ni con la contraseña por defecto.\n"
          "       Posibles causas: (1) ya cambiaste la contraseña a mano: .env debe tener ESA contraseña;\n"
          "       (2) LANGFLOW_SUPERUSER no coincide con el usuario existente.", file=sys.stderr)
    sys.exit(2)

status, me = call("GET", "/api/v1/users/whoami", token=token)
if status != 200 or me.get("username") != USER:
    print(f"error: el superusuario existente es '{me and me.get('username')}', no '{USER}'. "
          "Ajusta LANGFLOW_SUPERUSER en .env.", file=sys.stderr)
    sys.exit(3)

status, _ = call("PATCH", f"/api/v1/users/{me['id']}/reset-password", body={"password": NEW}, token=token)
if status != 200:
    print(f"error: Langflow rechazó el cambio (HTTP {status}).", file=sys.stderr)
    sys.exit(4)

if not token_for(NEW):
    print("error: se cambió la contraseña pero el login con la nueva falla.", file=sys.stderr)
    sys.exit(5)
if token_for("langflow"):
    print("AVISO: la contraseña por defecto 'langflow' TODAVÍA entra. Revisa el usuario.", file=sys.stderr)
    sys.exit(6)
print(f"OK: contraseña de '{USER}' cambiada (autenticado por {how}); la de por defecto ya no entra.")
PY
)

printf '%s' "$PASSWORD" | docker compose --profile "$PROFILE" exec -T -e "LF_USER=$USERNAME" langflow python -c "$PYCODE"
echo "Siguiente paso: recrear Langflow con AUTO_LOGIN=false (despliegue o 'docker compose --profile $PROFILE up -d langflow')."
