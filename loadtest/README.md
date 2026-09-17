# Load testing — Flowsdone Gateway

Herramientas de prueba de esfuerzo, **deliberadamente fuera de `docker-compose.yml`**: Locust corre como un proceso Python separado (en tu laptop, en un runner de CI, o en un contenedor `docker run` suelto) que le pega al gateway por HTTP desde afuera — igual que le pegaría el tráfico real de Evolution API. No es un servicio del stack, no toca el compose, no se despliega con el resto.

**Elegí el servidor destino antes de nada** — todo el tooling lee el mismo par de variables (`TARGET_BASE_URL` para Locust/setup/cleanup, `VPS_HOST` para los scripts de chaos), así que cambiar de servidor es solo cambiar qué archivo de entorno cargás:

| Servidor | Archivo | `VPS_HOST` |
|---|---|---|
| Local (este docker-compose) | `.env.local` (copiar de `.env.local.example`) | vacío → los scripts de chaos corren `docker compose` directo, sin SSH |
| VPS de producción | `.env.vps` (copiar de `.env.vps.example`) | seteado → los scripts de chaos corren por SSH |

Cubre las 4 cosas que se quieren demostrar:

1. **Throughput sostenido** (mensajes/segundo) — `locustfile.py`
2. **Latencia bajo carga** (p50/p95/p99) — mismo run, Locust lo reporta solo
3. **Recuperación ante fallos** — `chaos_worker_restart.sh`, corrido en paralelo
4. **Escalado horizontal en vivo** — `chaos_scale_workers.sh`, corrido en paralelo

## Qué mide y qué NO mide

El test golpea `POST /webhooks/whatsapp` con payloads válidos de Evolution API, contra una `channel_connection` de prueba dedicada (ver abajo). Eso ejercita el camino real completo: **Gateway → Switchboard → Kafka → `kafka_inbound_worker`** (dequeue + claim de idempotencia), tal como lo describe la sección 2 del README principal.

Lo que **no** mide: la llamada real a Langflow/el LLM. El agente de prueba apunta a un `langflow_flow_id` que no existe a propósito — el mensaje llega hasta `ExecuteWorkflowUseCase`, falla ahí (`app/application/use_cases/execute_workflow.py`), y **no se comittea el offset** (`app/adapters/inbound/http/queue/kafka_consumer.py`: `commit()` solo se llama si el handler no lanzó excepción). Esto es intencional: aísla el test del costo real de tokens de LLM. **Corrección sobre una versión anterior de esta nota**: no hay retry-con-backoff en memoria ni DLQ real conectada (`DLQ_TOPIC` existe como setting en `env.example.txt` pero no está cableada en `kafka_consumer.py` ni en `workers/kafka/inbound/main.py`) — el consumidor loguea el fallo y sigue con el próximo mensaje del topic en la misma sesión; el offset sin comittear solo importa si el worker se reinicia o hay un rebalance, momento en el que ese mensaje puede volver a entregarse. Si en algún momento se quiere medir el pipeline completo incluyendo Langflow, hay que apuntar `langflow_flow_id` a un flow real y liviano (sin llamar a un modelo caro) — no lo hagas contra un flow de producción real.

## Antes de correr nada: leé esto

- **No hay rate limiting en el gateway** (ni en FastAPI ni en Traefik) — nada te va a frenar si mandás demasiada carga demasiado rápido. El único límite es la capacidad real del servidor.
- **El uvicorn de `dockers/Dockerfile.api` corre con `--reload` hardcodeado incluso en producción hoy** — un solo proceso, modo dev. Hay un fix sin mergear (`bugfix/api-reload-per-env`) que lo soluciona vía `API_RELOAD_FLAGS`. Correr el test de esfuerzo con `--reload` activo mide un servidor en modo desarrollo, no la arquitectura real de producción — decidí si mergear ese fix antes de tomar los números como definitivos para la junta.
- **Contra el VPS de producción, corré esto solo en una ventana coordinada**, monitoreando OpenSearch Dashboards / Langfuse en vivo, con alguien listo para abortar (`Ctrl+C` en locust corta el tráfico al instante). Local no tiene este riesgo — es el punto de partida recomendado antes de repetir contra el VPS.

## Setup

```bash
cd loadtest
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Si el venv falla con "ensurepip is not available" (falta python3-venv):
#   sudo apt install python3-venv   — o, más rápido para probar ya:
#   pip install --user --break-system-packages -r requirements.txt

cp .env.local.example .env.local   # o .env.vps.example -> .env.vps para apuntar al VPS
set -a; source .env.local; set +a   # (o: .env.vps) — el "set -a" es necesario:
                                     # sin él, `source` solo fija las variables
                                     # en el shell y locust (subproceso) no las ve.

# Crea el tenant/proyecto/agente/canal aislado para el test, en el servidor elegido
python setup_test_tenant.py --base-url "$TARGET_BASE_URL" --admin-key "$ADMIN_API_KEY"
```

## Cómo correrlo con seguridad

**Paso 1 — UI interactiva, carga baja, a mano.** Antes de automatizar nada, confirmá que el camino funciona:

```bash
locust -f locustfile.py --host "$TARGET_BASE_URL"
```

Abrí `http://localhost:8089`, arrancá con 5 usuarios / spawn rate 1, mirá el gráfico en vivo un par de minutos. Confirmá en los logs del gateway (`docker compose logs -f api`) que los mensajes están llegando y no hay 401/500 inesperados.

**Paso 2 — Rampa escalonada, sin supervisión constante.** `GradualRampShape` en `locustfile.py` sube de a etapas (5 → 25 → 75 → 150 usuarios) con minutos de sostenimiento entre cada una — pensado para que haya tiempo de reaccionar entre escalón y escalón:

```bash
LOADTEST_SHAPE=1 locust -f locustfile.py --host "$TARGET_BASE_URL" --headless --csv=report
```

`LOADTEST_SHAPE=1` activa `GradualRampShape` (5→25→75→150, ver más abajo). **Sin esa variable, la clase ni se define — locust respeta `-u`/`-r` en vez de ignorarlos.** Ojo: definir *cualquier* `LoadTestShape` en el archivo hace que locust ignore `-u`/`-r` por completo, headless o no — nos pasó (un burst pensado como `-u 100` corrió en realidad a la concurrencia de la etapa 1 del shape, 5 usuarios, porque el shape estaba siempre activo).

Esto genera `report_stats.csv` (throughput y latencia p50/p66/p75/p80/p90/p95/p98/p99 por endpoint) y `report_stats_history.csv` (serie de tiempo) — de ahí sale directo el gráfico para el PPTX. Para ir más allá de 150 usuarios concurrentes, editá `STAGES` en `locustfile.py` — no lo subas a ciegas en el primer run contra prod.

**Importante — `-t/--run-time` de locust no es confiable para cortar solo (confirmado con locust 2.46.5: un run con `-t 30s` siguió mandando tráfico varios minutos después).** Envolvé siempre el comando con `timeout` del shell como mecanismo de corte real — crítico contra el VPS, donde un run que no corta solo es tráfico indefinido contra producción:

```bash
timeout 20m env LOADTEST_SHAPE=1 locust -f locustfile.py --host "$TARGET_BASE_URL" --headless --csv=results/report
```

Si `timeout` mata el proceso, el `_stats.csv` final puede quedar sin escribir — usá `results/report_stats_history.csv` (se escribe en vivo, cada pocos segundos) para leer los últimos números, o revisá el log completo.

**Paso 3 — Escenarios de caos, en paralelo al Paso 2 (otra terminal):**

```bash
# (ya con .env.local o .env.vps sourceado, según el servidor elegido arriba)

# Resiliencia: mata kafka_inbound_worker 60s a mitad del run
./chaos_worker_restart.sh

# Escalado horizontal: sube a 3 réplicas durante la etapa de mayor carga
REPLICAS=3 ./chaos_scale_workers.sh
```

Correlacioná los timestamps que imprimen estos scripts con `report_stats_history.csv` para ver el efecto exacto en el gráfico.

## Cleanup

```bash
python cleanup_test_tenant.py --admin-key "$ADMIN_API_KEY"
```

Borra el tenant/proyecto/agente/canal de prueba. Los mensajes de prueba que fallaron por el `langflow_flow_id` inexistente quedan con el offset sin comittear en `inbound.messages` — no hay DLQ real a la que se muevan (ver nota más arriba). Es ruido esperado del test, no un bug; si en algún momento se quiere resetear el offset del grupo `workflow-workers` a mano, es un `kafka-consumer-groups.sh --reset-offsets` estándar contra el topic.

## Tests

```bash
pip install -r requirements.txt
pytest loadtest/tests -q
```

Valida que el payload que arma `payloads.py` siga teniendo exactamente la forma que lee `whatsapp_evolution.py` — si ese handler cambia de forma incompatible, estos tests fallan en vez de que el load test se ponga a generar tráfico silenciosamente ignorado.
