# API Gateway FlowsDone

Gateway de mensajería multicanal (webchat, WhatsApp) con arquitectura hexagonal, orquestación de IA vía Langflow, automatización vía n8n, y stack completo de observabilidad. Corre en local con Docker Compose y escala a producción cambiando de perfil (`dev` → `prod`).

---

## Tabla de contenidos

1. [Qué hace este proyecto](#1-qué-hace-este-proyecto)
2. [Arquitectura](#2-arquitectura)
3. [Servicios](#3-servicios)
4. [Perfiles de Docker (dev / prod)](#4-perfiles-de-docker-dev--prod)
5. [Requisitos previos](#5-requisitos-previos)
6. [Puesta en marcha](#6-puesta-en-marcha)
7. [Bases de datos](#7-bases-de-datos)
8. [URLs locales (dev)](#8-urls-locales-dev)
9. [Dominios de producción (prod, vía Traefik)](#9-dominios-de-producción-prod-vía-traefik)
10. [Evolution API — puesta a tono](#10-evolution-api--puesta-a-tono)
11. [n8n + Langflow — cómo se integran](#11-n8n--langflow--cómo-se-integran)
12. [Observabilidad](#12-observabilidad)
13. [Troubleshooting](#13-troubleshooting)
14. [Mantenimiento](#14-mantenimiento)

---

## 1. Qué hace este proyecto

Es un **API Gateway** (`api_gateway/app/`, FastAPI, arquitectura hexagonal — ver `CLAUDE.md`) que recibe mensajes desde distintos canales (webchat propio, WhatsApp vía Evolution API) y los enruta a un workflow de **Langflow** para generar la respuesta con un LLM. El transporte entre el gateway y los workers es intercambiable: **Kafka** o **RabbitMQ**, ambos con workers dedicados de inbound/outbound (`workers/`).

- **Langflow** es el único lugar donde vive la orquestación de IA (agentes, prompts, RAG contra Weaviate).
- **n8n** es solo para automatización/triggers (webhooks, cron, integraciones) — **no** usa su nodo AI Agent; si un workflow de n8n necesita IA, le pega a Langflow por HTTP (`LANGFLOW_BASE_URL`).
- **Langfuse** traza cada ejecución de Langflow (tokens, latencia, costos).
- **OpenSearch + OTel Collector** centralizan logs de *todos* los contenedores del stack (no solo la app) y trazas OTLP de los servicios instrumentados.
- **Traefik** expone todo por dominio con HTTPS, pero solo en producción.

---

## 2. Arquitectura

```
                        ┌──────────────────────────────────────────┐
                        │              flowsdone-net                │
                        │        (única red, dev y prod)            │
                        └──────────────────────────────────────────┘

  Canales de entrada                Gateway (api_gateway/app/, hexagonal)
  ┌───────────┐                     ┌──────────────────────────┐
  │  Webchat   │──── WS/HTTP ──────▶│   api  (FastAPI :8000)   │
  │ (estático, │                     │  domain/application/     │
  │  servido   │                     │  adapters                │
  │  por api)  │                     └─────────────┬────────────┘
  └───────────┘                                    │
  ┌───────────┐        AMQP/webhook                │ publica en Kafka o RabbitMQ
  │ Evolution  │───────────────────────────────────▶│
  │ API (WA)   │                                    │
  └───────────┘                             ┌───────┴────────┐
                                             ▼                ▼
                                  ┌──────────────┐   ┌──────────────────┐
                                  │    Kafka      │   │     RabbitMQ      │
                                  └──────┬────────┘   └─────────┬─────────┘
                                         ▼                      ▼
                          kafka_inbound_worker         rabbitmq_inbound_worker
                                         │                      │
                                         └──────────┬───────────┘
                                                     ▼
                                          ┌────────────────────┐
                                          │      Langflow       │──▶ Langfuse (tracing)
                                          │  (orquestación IA)  │──▶ Weaviate (RAG)
                                          └──────────┬──────────┘
                                                     ▼
                          kafka_outbound_worker / rabbitmq_outbound_worker
                                                     │
                                                     ▼
                                       api (/internal/outbound) → WS al cliente

  Automatización (aparte, sin tocar el flujo de mensajes de arriba)
  ┌──────┐   HTTP Request node   ┌──────────┐
  │ n8n   │──────────────────────▶│ Langflow │   (n8n NO usa el nodo AI Agent)
  └──────┘                       └──────────┘

  Observabilidad (solo profile prod)
  Todos los contenedores ──logs (docker)──▶ otel-collector ──▶ OpenSearch ──▶ OpenSearch Dashboards
  api + workers + n8n + evolution ──OTLP (logs/traces)──▶ otel-collector ┘

  Proxy (solo profile prod)
  Traefik (file provider, traefik-dynamic.yml) ──▶ HTTPS por dominio ──▶ cada servicio
```

---

## 3. Servicios

| Servicio | Imagen / build | Rol |
|---|---|---|
| `api` | build (`dockers/Dockerfile.api`) | Gateway FastAPI: ingesta HTTP/WS, publica a Kafka/RabbitMQ, sirve el webchat estático y `/internal/outbound` |
| `kafka_inbound_worker` / `kafka_outbound_worker` | build (`dockers/Dockerfile.worker`) | Consumen/publican en Kafka, llaman a Langflow, entregan la respuesta |
| `rabbitmq_inbound_worker` / `rabbitmq_outbound_worker` | build (`dockers/Dockerfile.worker`) | Igual que arriba pero sobre RabbitMQ |
| `langflow` | build (`dockers/Dockerfile.langflow`) | Orquestación de IA — el único lugar con lógica de agentes/prompts |
| `n8n` | `n8nio/n8n:2.22.2` | Automatización/triggers. Llama a Langflow por HTTP, no usa AI Agent |
| `evolution` | build (`./evolution-api`, vendorizado) | Gateway de WhatsApp (Evolution API v2.3.7) |
| `langfuse-web` / `langfuse-worker` | `langfuse/langfuse:3.180.0` / `-worker:3` | Tracing y observabilidad de LLMs |
| `postgres` | `postgres:17-alpine` | DB principal: `gatewaydb`, `langfusedb`, `langflowdb`, `evolutiondb`, `n8ndb` |
| `redis` | `redis:7-alpine` | Cache compartido (Langfuse, Evolution) |
| `redis-insight` | `redis/redisinsight:3.4` | UI de Redis |
| `rabbitmq` | `rabbitmq:3.12-management-alpine` | Broker AMQP |
| `rabbitmq-scout` | `ghcr.io/ralve-org/rabbitscout` | UI de RabbitMQ (alternativa a la mgmt UI nativa) |
| `kafka` | `apache/kafka:4.2.1` | Broker Kafka (KRaft, sin Zookeeper) |
| `weaviate` | `semitechnologies/weaviate:1.37.0` | Vector DB para RAG |
| `weaviate-gui` | build (GitHub `Shah91n/WeaviateDB-Cluster-WebApp`) | UI de Weaviate |
| `clickhouse` | `clickhouse/clickhouse-server:26.3` | Almacén OLAP de Langfuse |
| `minio` | `minio/minio` | S3-compatible, storage de eventos/media de Langfuse |
| `opensearch`¹ | `opensearchproject/opensearch:2.12.0` | Almacén de logs/trazas |
| `opensearch-dashboards`¹ | `opensearchproject/opensearch-dashboards:2.12.0` | UI de logs (Discover) |
| `otel-collector`¹ | `otel/opentelemetry-collector-contrib:0.116.1` | Recolecta logs Docker de *todos* los contenedores + OTLP de las apps, exporta a OpenSearch |
| `traefik`¹ | `traefik:v3.3` | Reverse proxy HTTPS por dominio (file provider) |

¹ Solo corren en `profile: prod` — ver sección 4.

---

## 4. Perfiles de Docker (dev / prod)

El compose usa el anchor `x-common` con `profiles: [dev, prod]`, heredado por todos los servicios. **`opensearch`, `opensearch-dashboards`, `otel-collector` y `traefik`** lo overridean a `profiles: [prod]` — no se necesitan en desarrollo local.

`COMPOSE_PROFILES=dev` está seteado por defecto en `.env`, así que:

```bash
docker compose up -d
# equivalente a: docker compose --profile dev up -d
```

...levanta **todo excepto** el stack de observabilidad y Traefik.

Para levantar todo (incluyendo prod):

```bash
COMPOSE_PROFILES=prod docker compose up -d
# o:
docker compose --profile prod up -d
```

> **Importante:** editar `.env` **no** actualiza contenedores ya corriendo. Hace falta recrearlos:
> `docker compose up -d --force-recreate <servicio>` (o el stack completo). `docker compose restart` **no** relee `env_file`.

---

## 5. Requisitos previos

- Docker ≥ 24.x
- Docker Compose plugin ≥ 2.x
- `openssl` (para generar secrets si hace falta regenerarlos)

```bash
docker --version
docker compose version
```

---

## 6. Puesta en marcha

```bash
# 1. Variables de entorno
cp env.example.txt .env
# Revisar y cambiar TODAS las contraseñas/secrets marcadas "ChangeMe..." antes de usar en producción.

# 2. Levantar en modo dev
docker compose up -d

# 3. Ver estado
docker compose ps

# 4. Logs de un servicio
docker compose logs -f api
docker compose logs -f rabbitmq_inbound_worker
```

Para producción, además necesitás:
- Completar `SSL_EMAIL` en `.env` (Let's Encrypt lo requiere).
- Que los dominios `DOMAIN_*` apunten (DNS) a la IP pública de este host.
- Ajustar los dominios en `traefik-dynamic.yml` si difieren de los que trae por defecto (ver sección 9 — Traefik usa el **file provider**, no lee variables de `.env` ni labels de Docker).

```bash
docker compose --profile prod up -d
```

---

## 7. Bases de datos

`init-db.sh` crea automáticamente, **al primer arranque** de Postgres (volumen vacío), todas las bases listadas en `POSTGRES_MULTIPLE_DATABASES` del `.env` (`gatewaydb,langfusedb,langflowdb,evolutiondb,n8ndb`).

Si Postgres **ya tenía datos** y agregaste una base nueva a esa variable, el script no se vuelve a correr solo. Hay que crearla a mano, sin perder el resto de los datos:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE nombre_db"'
```

Verificar:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "\l"'
```

---

## 8. URLs locales (dev)

| Servicio | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| Webchat (demo) | http://localhost:8000/static/webchat/ |
| Langflow | http://localhost:7860 |
| Langfuse | http://localhost:4100 |
| n8n | http://localhost:5678 |
| Evolution API | http://localhost:8082 |
| Evolution Manager | http://localhost:8082/manager |
| Weaviate (API) | http://localhost:8080 |
| Weaviate GUI | http://localhost:8501 |
| RedisInsight | http://localhost:5540 |
| RabbitMQ Management (nativo) | http://localhost:15672 (solo `127.0.0.1`) |
| RabbitMQ Scout | http://localhost:3001 |
| MinIO Console | http://localhost:9083 |
| ClickHouse (HTTP) | http://localhost:8125 |
| Postgres | `localhost:5432` |

Solo con `--profile prod` (o `COMPOSE_PROFILES=prod`):

| Servicio | URL |
|---|---|
| OpenSearch | https://localhost:9200 |
| OpenSearch Dashboards | http://localhost:5601 |
| OTel Collector | gRPC `:4317` / HTTP `:4318` |
| Traefik | `:80` / `:443` |

---

## 9. Dominios de producción (prod, vía Traefik)

Traefik usa el **file provider** (`traefik-dynamic.yml`), no el Docker provider — los labels `traefik.*` que puedan aparecer en el compose **no tienen efecto**. Los dominios reales están hardcodeados en `traefik-dynamic.yml`; las variables `DOMAIN_*` del `.env` son solo referencia/documentación y **no** se leen automáticamente. Si cambiás un dominio, actualizalo en los dos lugares.

| Servicio | Dominio |
|---|---|
| n8n | https://auto.flowsdone.com |
| Langfuse | https://langfuse.flowsdone.com |
| Evolution API | https://evo.flowsdone.com |
| Webchat / API Gateway | https://chat.flowsdone.com |
| MinIO Console | https://buckets.flowsdone.com |
| RedisInsight | https://cache.flowsdone.com |
| RabbitMQ Scout | https://broker.flowsdone.com |
| Weaviate GUI | https://vector.flowsdone.com |
| OpenSearch Dashboards | https://logs.flowsdone.com |

---

## 10. Evolution API — puesta a tono

A diferencia de otros setups de Evolution API, acá el código **ya está vendorizado** en `./evolution-api/` (fork del repo oficial, v2.3.7) — no hace falta clonarlo aparte ni buildear manualmente.

```bash
# 1. Build (o se buildea solo con `docker compose up`)
docker compose build evolution

# 2. Asegurate de que evolutiondb exista (ver sección 7)

# 3. Levantar
docker compose up -d evolution

# 4. Verificar que responde
curl -H "apikey: $EVOLUTION_API_KEY" http://localhost:8082/
# {"status":200,"message":"Welcome to the Evolution API...", ...}
```

Al arrancar corre las migraciones de Prisma solo. Conecta contra el mismo `postgres`/`redis`/`rabbitmq` del stack (no levanta infra propia):
- DB propia: `evolutiondb`.
- Redis: con password (`CACHE_REDIS_URI` incluye `${REDIS_PASSWORD}` — la instancia de Evolution API por defecto no espera password, ojo si copiás config de otro lado).
- RabbitMQ: exchange propio `evolution_exchange` (no pisa `inbound.messages`/`outbound.messages` del gateway). `RABBITMQ_ENABLED=true`, así que cada evento de WhatsApp también se publica ahí — útil si más adelante querés consumirlo desde un worker propio en vez de (o además de) n8n.
- `N8N_ENABLED=false` — no hay integración nativa n8n↔Evolution activada todavía (ver sección 11 sobre cómo conectarían).

### Crear una instancia de WhatsApp

1. Entrá a http://localhost:8082/manager.
2. Creá una instancia nueva, usando `EVOLUTION_API_KEY` como API key global.
3. Escaneá el QR con WhatsApp (Dispositivos vinculados) para conectar el número.

---

## 11. n8n + Langflow — cómo se integran

n8n **no** tiene el nodo AI Agent en el flujo recomendado de este proyecto. La orquestación de IA vive enteramente en Langflow. Para que un workflow de n8n dispare un flujo de Langflow:

- Variables ya inyectadas en el contenedor de n8n: `LANGFLOW_BASE_URL` (`http://langflow:7860` interno) y `LANGFLOW_API_KEY`.
- En un nodo **HTTP Request**:
  - URL: `{{$env.LANGFLOW_BASE_URL}}/api/v1/run/<flow_id>`
  - Method: `POST`
  - Body (JSON): `{"input_value": "...", "output_type": "chat", "input_type": "chat", "session_id": "..."}`
  - **Importante:** `input_value` va en la **raíz** del body, no anidado bajo `"input"` — un error así hace que Langflow ignore el mensaje real y devuelva la respuesta por defecto del flujo (ver sección 13).

Las ejecuciones de n8n emiten trazas OTLP (`N8N_OTEL_TRACING_ENABLED=true`) hacia el mismo `otel-collector` que usa el resto del stack (solo visibles en `profile prod`).

Evolution API todavía no está conectado a n8n (`EVOLUTION_N8N_ENABLED=false`); si se quiere automatizar WhatsApp vía n8n, ese es el próximo paso natural (webhook de Evolution → n8n → Langflow).

---

## 12. Observabilidad

Solo activa en `profile prod`. Dos fuentes distintas confluyen en el mismo índice de OpenSearch (`ss4o_logs-*`):

1. **Logs de infraestructura**: el `otel-collector` lee `/var/lib/docker/containers/*/*.log` (el log driver `json-file` de Docker) de **todos** los contenedores del host — Postgres, Redis, RabbitMQ, Langflow, Langfuse, etc. — sin necesidad de instrumentarlos.
2. **Logs + traces de las apps propias**: `api` y los 4 workers están instrumentados con `opentelemetry-sdk` (ver `api_gateway/app/core/logging.py`), exportan por OTLP con `service.name` propio (`fd-gateway`, `fd-kafka-inbound-worker`, etc.), incluyendo `correlation_id` y ubicación en código (`code.file.path`/`line.number`). `n8n` y `evolution` también mandan sus propias trazas OTLP.

Para explorarlos: http://localhost:5601 (usuario `admin`, password `OPENSEARCH_PASSWORD`) → Discover → index pattern `ss4o_logs-*`.

> Nota multi-tenancy: OpenSearch Dashboards tiene tenants (Global/Private). Si no ves datos aunque el índice tenga documentos, revisá el selector de tenant arriba a la derecha — los index patterns quedan atados al tenant en el que estabas parado cuando los creaste.

---

## 13. Troubleshooting

### Cambié el `.env` pero el contenedor sigue con el valor viejo

`docker compose restart` no relee `env_file`. Hay que recrear:

```bash
docker compose up -d --force-recreate <servicio>
```

### Agregué una DB a `POSTGRES_MULTIPLE_DATABASES` pero no existe

`init-db.sh` solo corre en el primer arranque (volumen vacío de Postgres). Si Postgres ya tenía datos, creala a mano (sección 7) — no recrees el contenedor con `-v` o perdés todo lo demás.

### Langflow siempre responde el mismo mensaje genérico, sin importar el input

El caller le está mandando `input_value` anidado bajo `"input"` en vez de en la raíz del JSON. Langflow usa el valor por defecto (vacío) y el flujo responde su saludo/fallback. El formato correcto:

```json
{"input_value": "mensaje real", "output_type": "chat", "input_type": "chat", "session_id": "..."}
```

### Langfuse crashea en loop / "JavaScript heap out of memory"

V8 necesita headroom bajo el límite del contenedor. No bajar `LANGFUSE_MEM_LIMIT`/`LANGFUSE_WORKER_MEM_LIMIT` de ~2560m, y mantener `NODE_OPTIONS=--max-old-space-size=2048` en el environment de `langfuse-web`.

### No llegan logs/traces al `otel-collector` desde otros contenedores

El receiver OTLP tiene que bindear explícitamente a `0.0.0.0` en `otel-collector-config.yaml` (`endpoint: 0.0.0.0:4317` / `:4318`). Si queda en el default (`localhost`), nada fuera del propio contenedor le puede pegar — el síntoma es `Failed to export logs batch due to timeout` en los logs de la app que intenta exportar.

### No veo nada en OpenSearch Dashboards aunque el índice tiene documentos

Revisá el tenant activo (selector arriba a la derecha, ícono de persona). Los index patterns creados vía API sin el header `securitytenant: global` quedan en el tenant "Private" del usuario que los creó, invisibles para otra sesión/tenant.

### Evolution API — error de autenticación en Prisma

Asegurate de usar `DATABASE_CONNECTION_URI` (no `DATABASE_URL`) en el environment del servicio — es lo que espera este fork.

### Traefik no rutea un dominio nuevo

Confirmá que agregaste el router **y** el service en `traefik-dynamic.yml` (no alcanza con la variable `DOMAIN_*` del `.env` — Traefik no la lee, ver sección 9).

---

## 14. Mantenimiento

**Persistencia:** los volúmenes con datos reales están en `./volumes/` (bind mounts) y como named volumes de Docker (`redis_data`, `clickhouse_data`, `opensearch_data`, `n8n_data`, `redisinsight_data`). Backup de `./volumes/` + `docker volume` cubre el estado completo.

**Actualizar la imagen de un servicio:**

```bash
# Cambiar la versión en .env (ej. LANGFUSE_IMAGE), luego:
docker compose pull <servicio>
docker compose up -d --force-recreate <servicio>
```

**Parar sin borrar datos:**

```bash
docker compose down
```

**Parar y borrar named volumes (⚠️ no borra `./volumes/`, pero sí `redis_data`, `n8n_data`, etc.):**

```bash
docker compose down -v
```

**Recrear todo el stack tras editar `.env` o `docker-compose.yml`:**

```bash
docker compose up -d --force-recreate --remove-orphans
```


OJO IMPORTANTE PARA CREAR UNA COLLECION NUEVA EN WEAVIATE USAR LA API

curl -X POST http://localhost:8080/v1/schema \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TU_API_KEY_AQUI" \
  -d '{
    "class": "NOMBRE_COLLECCION",
    "vectorizer": "none",
    "replicationConfig": {
      "factor": 1
    }
  }'

CREATE USER fibralan_user WITH PASSWORD '15WB4FV4d0xn';


