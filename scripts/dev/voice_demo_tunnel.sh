#!/usr/bin/env bash
# Dev-only helper: exposes the local api:8000 stack publicly via a
# Cloudflare quick tunnel (no account/domain needed) so Twilio can
# reach /webhooks/voice for the browser softphone demo
# (static/voice_demo/). Not used in production - PUBLIC_BASE_URL there
# is the real domain, routed through the deployed Traefik.
#
# Usage:
#   scripts/dev/voice_demo_tunnel.sh start
#   scripts/dev/voice_demo_tunnel.sh stop
#
# "start" temporarily overwrites PUBLIC_BASE_URL in .env with the
# tunnel's URL, recreates the api container so it picks it up, and
# points the Twilio TwiML App (VOICE_DEMO_TWILIO_TWIML_APP_SID) at the
# tunnel. "stop" reverts all of that.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
CLOUDFLARED_BIN="$SCRIPT_DIR/cloudflared"
LOG_FILE="/tmp/voice_demo_tunnel.log"
PID_FILE="/tmp/voice_demo_tunnel.pid"
BACKUP_FILE="/tmp/voice_demo_tunnel.public_base_url.bak"

require_cloudflared() {
  if [ ! -x "$CLOUDFLARED_BIN" ]; then
    echo "Descargando cloudflared..."
    curl -sL -o "$CLOUDFLARED_BIN" \
      "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    chmod +x "$CLOUDFLARED_BIN"
  fi
}

get_env_var() {
  grep -oP "(?<=^$1=).*" "$ENV_FILE"
}

set_env_var() {
  # Portable in-place edit (works whether the key already exists or not).
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

cmd_start() {
  require_cloudflared

  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "El túnel ya está corriendo (PID $(cat "$PID_FILE")). Usa 'stop' primero." >&2
    exit 1
  fi

  get_env_var PUBLIC_BASE_URL > "$BACKUP_FILE"
  echo "PUBLIC_BASE_URL actual respaldado: $(cat "$BACKUP_FILE")"

  echo "Levantando túnel Cloudflare..."
  : > "$LOG_FILE"
  nohup "$CLOUDFLARED_BIN" tunnel --url http://localhost:8000 >>"$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  tunnel_url=""
  for _ in $(seq 1 30); do
    tunnel_url="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG_FILE" | head -n1 || true)"
    [ -n "$tunnel_url" ] && break
    sleep 1
  done

  if [ -z "$tunnel_url" ]; then
    echo "No se pudo obtener la URL del túnel, revisa $LOG_FILE" >&2
    exit 1
  fi

  echo "Túnel listo: $tunnel_url"

  set_env_var PUBLIC_BASE_URL "$tunnel_url"
  echo "PUBLIC_BASE_URL actualizado en .env, recreando el contenedor api..."
  (cd "$REPO_ROOT" && docker compose up -d --force-recreate api >/dev/null)

  echo "Esperando a que api levante..."
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null --max-time 2 "http://localhost:8000/voice-demo/token"; then
      break
    fi
    sleep 1
  done

  admin_key="$(get_env_var ADMIN_API_KEY)"
  account_sid="$(get_env_var VOICE_DEMO_TWILIO_ACCOUNT_SID)"
  twiml_app_sid="$(get_env_var VOICE_DEMO_TWILIO_TWIML_APP_SID)"

  auth_token="$(curl -s -H "X-Admin-Api-Key: $admin_key" \
    "http://localhost:8000/internal/admin/channel-apps/twilio/credentials" \
    | jq -r '.credentials.auth_token')"

  echo "Apuntando el TwiML App de Twilio ($twiml_app_sid) al túnel..."
  curl -s -u "$account_sid:$auth_token" \
    -X POST "https://api.twilio.com/2010-04-01/Accounts/$account_sid/Applications/$twiml_app_sid.json" \
    --data-urlencode "VoiceUrl=$tunnel_url/webhooks/voice" \
    --data-urlencode "VoiceMethod=POST" >/dev/null

  echo ""
  echo "Listo. Abre en tu navegador:"
  echo "  $tunnel_url/static/voice_demo/index.html"
  echo ""
  echo "Para revertir: scripts/dev/voice_demo_tunnel.sh stop"
}

cmd_stop() {
  if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Túnel detenido."
  else
    echo "No hay túnel corriendo (o ya se detuvo)."
  fi

  if [ -f "$BACKUP_FILE" ]; then
    original_url="$(cat "$BACKUP_FILE")"
    set_env_var PUBLIC_BASE_URL "$original_url"
    rm -f "$BACKUP_FILE"
    echo "PUBLIC_BASE_URL restaurado a $original_url, recreando api..."
    (cd "$REPO_ROOT" && docker compose up -d --force-recreate api >/dev/null)
    echo "Listo."
  fi
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  *)
    echo "Uso: $0 {start|stop}" >&2
    exit 1
    ;;
esac
