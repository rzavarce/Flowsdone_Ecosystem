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
7. [Bases de datos y migraciones](#7-bases-de-datos-y-migraciones)
8. [Multi-tenancy: tenants, proyectos, agentes y canales](#8-multi-tenancy-tenants-proyectos-agentes-y-canales)
9. [Webhooks por canal](#9-webhooks-por-canal)
10. [URLs locales (dev)](#10-urls-locales-dev)
11. [Dominios de producción (prod, vía Traefik)](#11-dominios-de-producción-prod-vía-traefik)
12. [Evolution API — puesta a tono](#12-evolution-api--puesta-a-tono)
13. [n8n + Langflow — cómo se integran](#13-n8n--langflow--cómo-se-integran)
14. [Observabilidad](#14-observabilidad)
15. [Troubleshooting](#15-troubleshooting)
16. [Mantenimiento](#16-mantenimiento)
17. [Tests](#17-tests)
18. [Canal de voz (Twilio ConversationRelay)](#18-canal-de-voz-twilio-conversationrelay)
19. [Softphone de prueba (demo)](#19-softphone-de-prueba-demo)
20. [Switchboard + Session (centralita de conmutación)](#20-switchboard--session-centralita-de-conmutación)

---

## 1. Qué hace este proyecto

Es un **API Gateway** (`api_gateway/app/`, FastAPI, arquitectura hexagonal — ver `CLAUDE.md`) multi-tenant que recibe mensajes desde distintos canales (webchat propio, Facebook Messenger, Instagram, X/Twitter, WhatsApp vía Evolution API, Telegram, TikTok, voz vía Twilio — sección 18) y los enruta según una regla fija:

- **Mensajería conversacional de cualquier canal → siempre Kafka → Langflow.** Todo webhook de canal (sección 9) resuelve a qué tenant/proyecto/agente pertenece y publica en Kafka; `kafka_inbound_worker` ejecuta el agente en Langflow y la respuesta vuelve por WebSocket/callback. El canal de voz sigue la misma regla pero con un topic y un worker propios (`VOICE_KAFKA_TOPIC` / `kafka_voice_worker`, sección 18) para no competir con los canales de texto.
- **Disparo de automatizaciones de n8n → siempre RabbitMQ.** El endpoint genérico `/webhooks/generic` (o cualquier caller interno) publica en RabbitMQ; un workflow de n8n con un nodo **RabbitMQ Trigger** lo consume directamente (no pasa por Langflow) y puede responder publicando en la cola de salida (ver sección 13).

El gateway es **multi-tenant**: varios clientes (tenants), cada uno con sus propios proyectos, canales conectados (credenciales cifradas), agentes de Langflow y automatizaciones de n8n — ver sección 8.

- **Langflow** es el único lugar donde vive la orquestación de IA (agentes, prompts, RAG contra Weaviate).
- **n8n** es solo para automatización/triggers (webhooks, cron, integraciones) — **no** usa su nodo AI Agent; si un workflow de n8n necesita IA, le pega a Langflow por HTTP (`LANGFLOW_BASE_URL`).
- **Langfuse** traza cada ejecución de Langflow (tokens, latencia, costos) y también recibe las trazas OTLP de n8n (reenviadas por el `otel-collector`).
- **OpenSearch + OTel Collector** centralizan logs de *todos* los contenedores del stack (no solo la app) y trazas OTLP de los servicios instrumentados.
- **Traefik** expone todo por dominio con HTTPS, pero solo en producción.

---

## 2. Arquitectura

```
                        ┌──────────────────────────────────────────┐
                        │              flowsdone-net                │
                        │        (única red, dev y prod)            │
                        └──────────────────────────────────────────┘

  Canales de entrada (webhooks nativos, sección 9)         Gateway (api_gateway/app/, hexagonal)
  ┌────────────┬────────────┬─────────┬──────────┬────────┐   ┌──────────────────────────┐
  │  Webchat   │ Facebook / │ X /     │ WhatsApp │Telegram│   │   api  (FastAPI :8000)   │
  │  (WS)      │ Instagram  │ Twitter │(Evolution│/TikTok │──▶│  domain/application/     │
  │            │ (Graph API)│         │   API)   │        │   │  adapters                │
  └────────────┴────────────┴─────────┴──────────┴────────┘   └─────────────┬────────────┘
                                                                             │
                            Switchboard resuelve/crea la Session             │ transport="kafka"
                            (channel_type, external_id) → tenant/           │ SIEMPRE para canales
                            proyecto/agente (sección 8, 20)                 ▼
                                                                  ┌──────────────────┐
                                                                  │       Kafka        │
                                                                  └─────────┬──────────┘
                                                                            ▼
                                                                 kafka_inbound_worker
                                                                            │
                                                                            ▼
                                                                 ┌────────────────────┐
                                                                 │      Langflow       │──▶ Langfuse (tracing)
                                                                 │  (orquestación IA)  │──▶ Weaviate (RAG)
                                                                 └──────────┬──────────┘
                                                                            ▼
                                                                 kafka_outbound_worker
                                                                            │
                                                                            ▼
                                                          api (/internal/outbound) → WS al cliente

  Automatización de n8n (aparte, sin tocar el flujo de mensajes de arriba)
  ┌──────────────────┐   transport="rabbitmq"   ┌──────────┐   RabbitMQ Trigger node   ┌──────┐
  │ /webhooks/generic │─────────────────────────▶│ RabbitMQ │──────────────────────────▶│ n8n  │
  └──────────────────┘                           └──────────┘                           └──┬───┘
                                                       ▲                                     │
                                                       │      nodo RabbitMQ (publish)         │
                                                       └─────────── outbound.messages ◀───────┘
                                                                            │
                                                       rabbitmq_outbound_worker (ya existente)
                                                                            │
                                                                            ▼
                                                          api (/internal/outbound) → WS al cliente

  n8n también puede llamar a Langflow por HTTP si un workflow necesita IA (NO usa el nodo AI Agent, ver sección 13)

  Observabilidad (solo profile prod)
  Todos los contenedores ──logs (docker)──▶ otel-collector ──▶ OpenSearch ──▶ OpenSearch Dashboards
  api + workers + n8n + evolution ──OTLP (logs/traces)──▶ otel-collector ──▶ OpenSearch
                                                              └──▶ Langfuse (traces, vía OTLP público)

  Proxy (solo profile prod)
  Traefik (file provider, traefik-dynamic.yml) ──▶ HTTPS por dominio ──▶ cada servicio
```

> 📞 **Canal de voz (no está en el diagrama de arriba, ver sección 18):** sigue el mismo principio (webhook → resolver tenant/proyecto/agente → Kafka → Langflow → entrega de vuelta), pero con su propio topic (`VOICE_KAFKA_TOPIC`) y worker dedicado (`kafka_voice_worker`), y con Twilio ConversationRelay haciendo STT/TTS por WebSocket en vez de un webhook de texto simple.

> ⚠️ **Caveat conocido:** `rabbitmq_inbound_worker` (heredado de antes de que existiera esta separación) sigue escuchando la misma cola/routing key (`rag_worker_queue` / `inbound.message`) y trata cualquier mensaje `transport=rabbitmq` como si fuera para Langflow. Mientras no se lo desactive, un mensaje dirigido a n8n también dispara (en paralelo) un intento fallido de `rabbitmq_inbound_worker` contra Langflow con un `workflow_id` que no existe ahí — no rompe nada, pero genera una segunda respuesta de error. Si no vas a usar el camino "RabbitMQ → Langflow" (no es el diseño de este proyecto), podés `docker compose stop rabbitmq_inbound_worker` con seguridad.

---

## 3. Servicios

| Servicio | Imagen / build | Rol |
|---|---|---|
| `api` | build (`dockers/Dockerfile.api`) | Gateway FastAPI: ingesta HTTP/WS, publica a Kafka/RabbitMQ, sirve el webchat estático y `/internal/outbound` |
| `kafka_inbound_worker` / `kafka_outbound_worker` | build (`dockers/Dockerfile.worker`) | Camino de mensajería (canales → Langflow): consumen/publican en Kafka, llaman a Langflow, entregan la respuesta |
| `rabbitmq_inbound_worker` / `rabbitmq_outbound_worker` | build (`dockers/Dockerfile.worker`) | `outbound` entrega al gateway la respuesta que publique un workflow de n8n. `inbound` es un remanente que también llama a Langflow sobre RabbitMQ — ver el caveat de la sección 2, hoy el camino real hacia n8n es el `RabbitMQ Trigger` node (sección 13) |
| `kafka_voice_worker` | build (`dockers/Dockerfile.worker`) | Canal de voz (Twilio, sección 18): consume `VOICE_KAFKA_TOPIC`, ejecuta el agente en Langflow y entrega la respuesta directo a `/internal/outbound` — un solo worker, no un par inbound/outbound como el resto |
| `langflow` | build (`dockers/Dockerfile.langflow`) | Orquestación de IA — el único lugar con lógica de agentes/prompts |
| `n8n` | `n8nio/n8n:2.33.3` | Automatización/triggers. Llama a Langflow por HTTP, no usa AI Agent |
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
- Ajustar los dominios en `traefik-dynamic.yml` si difieren de los que trae por defecto (ver sección 11 — Traefik usa el **file provider**, no lee variables de `.env` ni labels de Docker).

```bash
docker compose --profile prod up -d
```

---

## 7. Bases de datos y migraciones

`init-db.sh` crea automáticamente, **al primer arranque** de Postgres (volumen vacío), todas las bases listadas en `POSTGRES_MULTIPLE_DATABASES` del `.env` (`gatewaydb,langfusedb,langflowdb,evolutiondb,n8ndb`). Ya **no** crea tablas dentro de `gatewaydb` — eso lo gestiona Alembic.

Si Postgres **ya tenía datos** y agregaste una base nueva a esa variable, el script no se vuelve a correr solo. Hay que crearla a mano, sin perder el resto de los datos:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE nombre_db"'
```

Verificar:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "\l"'
```

### Migraciones de `gatewaydb` (Alembic)

El esquema de `gatewaydb` (`tenants`, `projects`, `agents`, `workflows`, `channel_connections`, `channel_apps`, `workflow_executions`) vive en `api_gateway/migrations/`, gestionado con Alembic (`api_gateway/alembic.ini`). No hay un servicio de Docker que las corra solo. En producción, `.github/workflows/deploy.yml` las corre automáticamente (`docker compose run --rm api alembic ... upgrade head`) después de buildear las imágenes y antes de levantar `api`/los workers. En local se aplican a mano:

```bash
# Desde la raíz del repo, contra el postgres del stack ya levantado
docker compose run --rm api alembic -c api_gateway/alembic.ini upgrade head

# Ver la revisión actual
docker compose run --rm api alembic -c api_gateway/alembic.ini current

# Crear una migración nueva después de tocar api_gateway/app/adapters/outbound/db/models.py
docker compose run --rm api alembic -c api_gateway/alembic.ini revision --autogenerate -m "descripción"
```

> **Importante:** `alembic.ini` resuelve `sqlalchemy.url` en runtime desde `settings.DATABASE_URL_SQLALCHEMY` (`api_gateway/app/core/config.py`), no está hardcodeado — no hace falta tocar el `.ini` para apuntar a otro entorno, alcanza con la variable de entorno.

---

## 8. Multi-tenancy: tenants, proyectos, agentes y canales

El gateway es un **SaaS multi-cliente**: cada tenant puede tener varios proyectos, cada proyecto sus propios agentes de Langflow, sus automatizaciones de n8n, y sus canales conectados (con credenciales propias). El modelo, de mayor a menor:

```
tenant (cliente)
 └─ project (ej. "Soporte", "Ventas")
     ├─ agent          → langflow_flow_id: qué flow de Langflow atiende los mensajes de este proyecto
     ├─ workflow        → n8n_workflow_id: automatización de n8n asociada al proyecto (informativo, no interviene en el routing de canales)
     └─ channel_connection → un canal conectado (Facebook Page, número de WhatsApp/instancia Evolution, bot de Telegram, etc.)
                             apunta a UN agent; sus credenciales (tokens, secrets) se guardan cifradas
```

La tabla `channel_connections` tiene una unique constraint `(channel_type, external_id)` — es la clave que usan los webhooks de la sección 9 para resolver, a partir del payload nativo de cada plataforma, a qué tenant/proyecto/agente pertenece un mensaje entrante. El `conversation_id` que llega a Langflow queda namespaced como `f"{project_id}:{channel_type}:{external_conversation_key}"` para que dos tenants no choquen aunque hablen con el mismo número/usuario.

Las credenciales de `channel_connections.credentials` se cifran con `cryptography.Fernet` antes de guardarse (`adapters/outbound/db/crypto.py`) usando `CHANNEL_CREDENTIALS_ENCRYPTION_KEY`. Generar una clave nueva:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### API de administración

Todo se gestiona vía HTTP en `/internal/admin/*`, protegido con el header `X-Admin-Api-Key` (valor = `ADMIN_API_KEY` del `.env`). CRUD completo (`POST`/`GET` colección, `GET`/`PATCH`/`DELETE` por id) para `tenants`, `projects`, `agents`, `workflows` y `channel-connections`. Los `GET` de `channel-connections` **nunca** devuelven `credentials` en claro (solo `has_credentials: bool`).

```bash
KEY="$ADMIN_API_KEY"   # el valor real está en .env

# 1. Tenant
curl -s -X POST http://localhost:8000/internal/admin/tenants \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","slug":"acme"}'

# 2. Proyecto (usar el id devuelto arriba)
curl -s -X POST http://localhost:8000/internal/admin/projects \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","name":"Soporte","slug":"soporte"}'

# 3. Agente (langflow_flow_id = id del flow en Langflow)
curl -s -X POST http://localhost:8000/internal/admin/agents \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"project_id":"<project_id>","name":"Agente Soporte","langflow_flow_id":"<flow_id>","is_default":true}'

# 4. Canal conectado (ejemplo WhatsApp vía Evolution API)
curl -s -X POST http://localhost:8000/internal/admin/channel-connections \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
        "project_id":"<project_id>",
        "agent_id":"<agent_id>",
        "channel_type":"whatsapp_evolution",
        "external_id":"<nombre-de-la-instancia-evolution>",
        "credentials":{"note":"lo que necesites guardar, se cifra automáticamente"}
      }'
```

Filtros disponibles: `GET /internal/admin/projects?tenant_id=...`, `GET /internal/admin/agents?project_id=...`, `GET /internal/admin/workflows?project_id=...`, `GET /internal/admin/channel-connections?project_id=...`.

---

## 9. Webhooks por canal

Cada canal tiene su propio endpoint HTTP que entiende el payload **nativo** de esa plataforma, lo verifica, resuelve el `channel_connection` (sección 8) y publica en Kafka hacia Langflow — nunca hace falta armar el envelope a mano (eso lo sigue haciendo `/webhooks/generic` para casos genéricos/n8n).

> El canal de voz (Twilio) sigue esta misma idea pero no encaja en la tabla de abajo (webhook + WebSocket de streaming, no un solo request/response) — documentado aparte en la sección 18.

| Canal | Ruta | Verificación | `external_id` (clave de lookup) |
|---|---|---|---|
| Facebook Messenger | `GET/POST /webhooks/facebook` | GET: `hub.verify_token` == `channel_apps.meta.webhook_verify_token`. POST: `X-Hub-Signature-256` (HMAC-SHA256 con `channel_apps.meta.app_secret`) | `entry[].id` (Page ID) |
| Instagram DM | `GET/POST /webhooks/instagram` | Igual que Facebook (misma Meta App, mismo `channel_apps.meta`) | `entry[].id` (IG Business Account ID) |
| X / Twitter | `GET/POST /webhooks/twitter` | GET: CRC challenge firmado con `channel_apps.twitter.consumer_secret`. POST: `X-Twitter-Webhooks-Signature` | `for_user_id` |
| WhatsApp (Evolution API) | `POST /webhooks/whatsapp` | Header `apikey` == `EVOLUTION_API_KEY` | `instance` (nombre de la instancia Evolution) |
| Telegram | `POST /webhooks/telegram/{bot_token}` | Header `X-Telegram-Bot-Api-Secret-Token` == `channel_connections.credentials.telegram_webhook_secret` de esa conexión | `{bot_token}` (path) |
| TikTok | `POST /webhooks/tiktok` | Header `TikTok-Signature` (HMAC-SHA256 con `channel_apps.tiktok.client_secret`) | `data.open_id` |

Si el `channel_connection` no existe para ese `(channel_type, external_id)` (canal sin registrar todavía en el admin API), el webhook responde `200` igual (para que la plataforma no reintente infinito) pero no publica nada — queda logueado como `*.not_routable`.

### Telegram: secret y `setWebhook` automáticos

Para Telegram, `POST /internal/admin/channel-connections` ya no requiere pasos manuales por curl:

- Si `credentials` no trae `telegram_webhook_secret`, se genera uno automáticamente (`RandomHexSecretGenerator`, equivalente a `openssl rand -hex 32`) antes de guardar la conexión.
- Inmediatamente después de crearla, se llama a `setWebhook` de la Bot API de Telegram (`TelegramWebhookRegistrar`) con `url={PUBLIC_BASE_URL}/webhooks/telegram/{bot_token}` y ese secret — no hace falta correr el curl de `setWebhook` a mano.
- Si Telegram rechaza el `setWebhook` (bot_token inválido, etc.), la conexión recién creada se borra y el endpoint devuelve `502` — nunca queda un `channel_connection` "fantasma" sin webhook real detrás.

Esta lógica vive en `CreateChannelConnectionUseCase` (`application/use_cases/create_channel_connection.py`), orquestando tres puertos intercambiables: `ChannelConnectionRepositoryPort` (persistencia), `SecretGeneratorPort` (generación del secret, reutilizable por cualquier canal futuro que lo necesite) y `WebhookRegistrarPort` (registro externo; ver `WebhookRegistrarFactory` para qué canales tienen implementación hoy — agregar uno nuevo es una entrada más ahí, sin tocar el use case).

`PATCH /internal/admin/channel-connections/{id}` (`UpdateChannelConnectionUseCase`) sigue la misma lógica cuando el body toca `credentials`: como el repositorio reemplaza `credentials` entero (no lo mergea), un `PATCH` que cambie credenciales sin reenviar `telegram_webhook_secret` preservaría — antes de este cambio, perdería — el secret existente, y si el secret sí cambia, vuelve a llamar a `setWebhook` para que Telegram quede sincronizado (si no, el bot empieza a devolver 401 en silencio). Si el registro falla, las credenciales se revierten a su valor anterior y el endpoint devuelve `502`.

`DELETE /internal/admin/channel-connections/{id}` (`DeleteChannelConnectionUseCase`) llama a `deleteWebhook` antes de borrar la fila, pero a diferencia de create/update es **best-effort**: si Telegram lo rechaza (bot ya borrado por el cliente, API caída, etc.) se loguea como warning y la fila se borra igual — el pedido explícito de borrar no debería quedar bloqueado por el estado de una plataforma externa.

### Facebook/Instagram: suscripción de página automática

`POST /internal/admin/channel-connections` con `channel_type: "facebook"` o `"instagram"` también auto-registra, pero de forma distinta a Telegram: Meta no necesita ningún secret generado por nosotros (la verificación del webhook ya usa el `app_secret` compartido de `channel_apps.meta`), así que `MetaWebhookRegistrar.secret_field` es `None` y no se genera nada. Lo que sí automatiza es la parte que hasta ahora era curl manual: `POST /{page_id}/subscribed_apps` de la Graph API (usando `credentials.page_access_token`, el mismo valor que ya usan `FacebookSender`/`InstagramSender` para enviar mensajes — sección 9), que le dice a Meta "esta página en particular debe mandarle eventos a nuestra app". Si `page_access_token` falta o la Graph API lo rechaza, la conexión recién creada se borra y el endpoint devuelve `502`, igual que con Telegram.

El `PATCH` re-suscribe la página cuando `credentials.page_access_token` cambia (revirtiendo si falla), y el `DELETE` desuscribe con el mismo criterio best-effort que Telegram.

`WebhookRegistrarPort.register()`/`deregister()` reciben el diccionario `credentials` completo (no un `secret` suelto), justamente para que cada canal pueda tomar lo que realmente necesita — el generado (`secret_field`) para Telegram, el `page_access_token` provisto por el admin para Meta — sin forzar a todos los canales a encajar en la forma de Telegram.

Falta configurar por fuera de este flujo (no automatizado, es setup de app, no por conexión): la App de Meta compartida (`channel_apps.meta`, sección 9) y su suscripción a nivel App en el dashboard de Meta (qué campos escucha el Webhooks product) — eso se hace una sola vez para todo el SaaS, no por `channel_connection`.

### Secrets de canal: App compartida (`channel_apps`) vs. credenciales por conexión

Hay dos categorías, y no son intercambiables:

- **Meta (Facebook+Instagram), X y TikTok firman *todos* los webhooks de *todas* las páginas/cuentas suscriptas con el secret de una sola App** — así funcionan esas plataformas, no es una limitación nuestra. El modelo de este SaaS es **una única App compartida por proveedor** para todos los tenants (igual que ManyChat/Chatfuel/Intercom): evita que cada cliente tenga que pasar por App Review/Business Verification de Meta solo para conectar su página. Estos secrets viven en la tabla `channel_apps` (cifrados igual que `channel_connections.credentials`), gestionable vía admin API — **ya no están en `.env`**:
  ```bash
  KEY="$ADMIN_API_KEY"

  # Facebook + Instagram comparten esta misma App
  curl -s -X PUT http://localhost:8000/internal/admin/channel-apps/meta \
    -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"credentials": {"app_secret": "...", "webhook_verify_token": "..."}}'

  curl -s -X PUT http://localhost:8000/internal/admin/channel-apps/twitter \
    -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"credentials": {"consumer_secret": "..."}}'

  curl -s -X PUT http://localhost:8000/internal/admin/channel-apps/tiktok \
    -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"credentials": {"client_secret": "..."}}'
  ```
  `GET /internal/admin/channel-apps` nunca expone `credentials` en claro (mismo patrón que `channel_connections`, solo `has_credentials: bool`).

- **Telegram es la excepción**: cada cliente tiene su propio bot, y Telegram permite un `secret_token` distinto por bot (configurado vía `setWebhook`). Por eso ese secret **no** va en `channel_apps` — va en `channel_connections.credentials.telegram_webhook_secret` de la conexión de ese cliente, igual que el resto de sus credenciales (sección 8).

Si mañana un cliente enterprise exige traer su propia App de Meta/X/TikTok en vez de usar la compartida, es un caso especial a resolver puntualmente (agregar el override en esa `channel_connection`) — no está soportado de forma genérica hoy.

**Otras variables de entorno relevantes:**

| Variable | Para qué |
|---|---|
| `ADMIN_API_KEY` | Header `X-Admin-Api-Key` del API de administración (sección 8) |
| `PUBLIC_BASE_URL` | URL pública del gateway (a diferencia de `GATEWAY_INTERNAL_URL`, que solo resuelve dentro de la red de Docker) — usada para armar la callback URL que Telegram registra vía `setWebhook` (ver sección 9) |
| `CHANNEL_CREDENTIALS_ENCRYPTION_KEY` | Clave Fernet para cifrar `channel_connections.credentials` **y** `channel_apps.credentials` |
| `EVOLUTION_API_KEY` | Shared secret del propio Evolution API — valida el header `apikey` del webhook de WhatsApp |
| `LANGFLOW_API_KEY` | **Obligatoria** para que `LangflowExecutor` autentique contra Langflow — ver troubleshooting (sección 15) |
| `KAFKA_TOPIC_PARTITIONS` | Particiones de `KAFKA_TOPIC`/`DLQ_TOPIC` (default `6`) — ver "Particiones de Kafka por canal" más abajo |

Hoy solo **WhatsApp (Evolution API)** tiene credenciales reales configuradas — Facebook/Instagram/X/TikTok están implementados y probados a nivel de verificación de firma, pero necesitan que cargues la App real de cada plataforma en `channel_apps` antes de recibir tráfico real; Telegram necesita un bot real con su `secret_token` en la `channel_connection` correspondiente.

### Envío outbound: la respuesta del workflow vuelve al canal de origen

El `MessageEnvelope` de cada mensaje entrante de un canal (no webchat) lleva
`meta.channel_connection_id` y `meta.external_conversation_key` (el
`remoteJid`/`psid`/`chat_id`/... del destinatario). Cuando Langflow
responde, ese mismo `envelope.meta` viaja intacto hasta
`HandleOutboundResponseUseCase.deliver()` (llamado desde
`/internal/outbound` tanto por `kafka_outbound_worker` como por
`rabbitmq_outbound_worker`), que resuelve el `channel_connection` y
despacha el mensaje al `ChannelSenderPort` correspondiente
(`api_gateway/app/adapters/outbound/channels/`):

| Canal | Envío | Credencial nueva requerida |
|---|---|---|
| WhatsApp (Evolution API) | `POST {EVOLUTION_API_BASE_URL}/message/sendText/{instance}` | Ninguna — reusa `EVOLUTION_API_KEY` global |
| Facebook Messenger | Graph API `POST /{page_id}/messages` | `channel_connections.credentials.page_access_token` |
| Instagram DM | Graph API `POST /{ig_account_id}/messages` | `channel_connections.credentials.page_access_token` |
| Telegram | `POST {TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage` | Ninguna — `external_id` ya es el bot_token |
| X / Twitter | — | **Stub**: loguea `channel.sender.not_implemented`. Requiere tier de pago de la API de X para DMs + firma OAuth1.0a (no implementada) |
| TikTok | — | **Stub**: loguea `channel.sender.not_implemented`. TikTok no tiene API pública de envío para apps de terceros fuera de Business Messaging |

Variables nuevas: `EVOLUTION_API_BASE_URL`, `META_GRAPH_API_BASE_URL`,
`META_GRAPH_API_VERSION`, `TELEGRAM_API_BASE_URL`.

Si el envío a un canal falla (credenciales faltantes, API externa caída,
etc.), queda logueado como `channel.sender.failed` / `handle.outbound.channel.deliver.failed`
— nunca rompe `/internal/outbound` ni reintenta automáticamente.

### Particiones de Kafka por canal (aislar fallas/carga sin sumar workers)

`IngestMessageUseCase` publica cada mensaje en `KAFKA_TOPIC` (`inbound.messages`) usando el **canal como `key`** de Kafka (`KafkaPublisher.publish(..., key=channel)`). Con eso, Kafka garantiza que todos los mensajes de un mismo canal (`whatsapp_evolution`, `facebook`, `web`, etc.) siempre caen en la **misma partición** y en orden — es la base para poder aislar canales entre sí más adelante, sin tener que definir un worker por canal.

- `api_gateway/app/infrastructure/kafka_admin.py` (`ensure_topics_exist()`) crea `KAFKA_TOPIC`/`DLQ_TOPIC` con `KAFKA_TOPIC_PARTITIONS` particiones (default `6`, env-configurable) si no existen, y **sube** la cantidad de particiones si el tópico ya existía con menos (Kafka no permite bajarlas). Corre solo, al arrancar `api` y los workers de Kafka — no hace falta tocar nada a mano salvo que quieras más de 6.
- **Hoy, con una sola réplica de `kafka_inbound_worker`**, esto no aísla nada todavía — un único proceso sigue consumiendo las 6 particiones. El aislamiento real se activa el día que escales réplicas del mismo worker:
  ```bash
  docker compose up -d --scale kafka_inbound_worker=3
  ```
  Kafka reparte automáticamente las particiones entre las réplicas activas del mismo `group_id` (`workflow-workers`). Si un canal tiene un pico o un flow lento, solo la réplica que atiende esa partición se ve afectada — las demás siguen sirviendo el resto de los canales sin cambiar una línea de código. Escalá esto según demanda real en producción, no antes.

---

## 10. URLs locales (dev)

| Servicio | URL |
|---|---|
| API Gateway | http://localhost:8000 |
| Webchat (demo) | http://localhost:8000/static/webchat/ (`?caso=langflow` o `?caso=n8n`, ver sección 13) |
| Admin API (tenants/proyectos/agentes/canales) | http://localhost:8000/internal/admin/* (sección 8) |
| Webhooks de canal | http://localhost:8000/webhooks/{facebook,instagram,twitter,whatsapp,telegram/{bot_token},tiktok} (sección 9) |
| Webhook de voz (Twilio) | http://localhost:8000/webhooks/voice — sin el nombre del proveedor en la ruta, a propósito (sección 18) |
| WebSocket de streaming de voz | ws://localhost:8000/voice/stream/{call_sid} (lo abre Twilio, no se usa a mano — sección 18) |
| Softphone de prueba (demo) | http://localhost:8000/static/voice_demo/ (sección 19) |
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

## 11. Dominios de producción (prod, vía Traefik)

Traefik usa el **file provider** (`traefik-dynamic.yml`), no el Docker provider — los labels `traefik.*` que puedan aparecer en el compose **no tienen efecto**. Los dominios reales están hardcodeados en `traefik-dynamic.yml`; las variables `DOMAIN_*` del `.env` son solo referencia/documentación y **no** se leen automáticamente. Si cambiás un dominio, actualizalo en los dos lugares.

| Servicio | Dominio |
|---|---|
| n8n | https://auto.flowsdone.com |
| Langfuse | https://langfuse.flowsdone.com |
| Evolution API | https://evo.flowsdone.com |
| Webchat (demo del widget) | https://chat.flowsdone.com |
| Admin API + Webhooks de canal | https://platform.flowsdone.com |
| MinIO Console | https://buckets.flowsdone.com |
| RedisInsight | https://cache.flowsdone.com |
| RabbitMQ Scout | https://broker.flowsdone.com |
| Weaviate GUI | https://vector.flowsdone.com |
| OpenSearch Dashboards | https://logs.flowsdone.com |

El canal de voz (sección 18) y su softphone de prueba (sección 19) no tienen dominio propio — cuelgan del mismo `platform.flowsdone.com` que ya usan el admin API y los webhooks de texto, sin reescritura de path.

---

## 12. Evolution API — puesta a tono

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

## 13. n8n + Langflow — cómo se integran

n8n **no** tiene el nodo AI Agent en el flujo recomendado de este proyecto. La orquestación de IA vive enteramente en Langflow. Hay dos integraciones, en direcciones opuestas:

### n8n → Langflow (un workflow de n8n necesita IA)

- Variables ya inyectadas en el contenedor de n8n: `LANGFLOW_BASE_URL` (`http://langflow:7860` interno) y `LANGFLOW_API_KEY`.
- En un nodo **HTTP Request**:
  - URL: `{{$env.LANGFLOW_BASE_URL}}/api/v1/run/<flow_id>`
  - Method: `POST`
  - Header: `x-api-key: {{$env.LANGFLOW_API_KEY}}` — **obligatorio**, ver sección 15.
  - Body (JSON): `{"input_value": "...", "output_type": "chat", "input_type": "chat", "session_id": "..."}`
  - **Importante:** `input_value` va en la **raíz** del body, no anidado bajo `"input"` — un error así hace que Langflow ignore el mensaje real y devuelva la respuesta por defecto del flujo.

### Gateway → n8n (el gateway dispara una automatización)

El gateway publica en RabbitMQ (`/webhooks/generic` con `transport: "rabbitmq"`, o cualquier caller que use `IngestMessageUseCase`). Un workflow de n8n lo recibe con un nodo **RabbitMQ Trigger** apuntando a la misma cola/exchange, y responde publicando en la cola de salida que el gateway ya escucha (`rabbitmq_outbound_worker`):

1. **Credencial RabbitMQ** en n8n: host `rabbitmq`, puerto `5672`, user/pass = `RABBITMQ_USER`/`RABBITMQ_PASS`, vhost `/`.
2. **RabbitMQ Trigger**: `Queue/Topic` = una cola propia (ej. `n8n_workflow_queue`) — **tiene que existir de antemano** (el nodo hace `checkQueue`, no la crea), bindeada al exchange `inbound.messages` con routing key `inbound.message`. Opción `JSON Parse Body` = true.
3. **Code node**: arma el envelope de respuesta a partir de `$input.item.json.content` (el mensaje ya parseado):
   ```js
   const received = $input.item.json.content;
   return { json: {
     meta: {
       message_id: 'n8n-' + Date.now(),
       timestamp: new Date().toISOString(),
       direction: 'outbound',
       conversation_id: received.meta.conversation_id,
       workflow_id: received.meta.workflow_id,
     },
     transport: 'rabbitmq',
     channel: received.channel,
     payload: { message: 'tu respuesta acá' },
     response_to: received.meta.message_id,
     version: 1,
   }};
   ```
4. **RabbitMQ node** (no Trigger): `Mode` = Exchange, `Exchange` = `outbound.messages`, `Type` = Topic, `Routing Key` = `outbound.message`, `Send Input Data` = false, `Message` = `={{ JSON.stringify($json) }}`. Esto lo recoge `rabbitmq_outbound_worker` (ya existente) y lo entrega al cliente por WS/`callback_url`.

Ver el caveat de la sección 2 sobre `rabbitmq_inbound_worker` compitiendo por la misma cola/routing key.

Las ejecuciones de n8n emiten trazas OTLP (`N8N_OTEL_ENABLED=true`, ver el gotcha de nombres de variable en la sección 15) hacia el mismo `otel-collector` que usa el resto del stack — se ven en OpenSearch (solo `profile prod`) **y** en Langfuse (el collector las reenvía también al endpoint OTLP público de Langfuse, ver sección 14).

Evolution API todavía no está conectado a n8n (`EVOLUTION_N8N_ENABLED=false`); si se quiere automatizar WhatsApp vía n8n, ese es el próximo paso natural (webhook de Evolution → n8n → Langflow).

---

## 14. Observabilidad

Solo activa en `profile prod`. Dos fuentes distintas confluyen en el mismo índice de OpenSearch (`ss4o_logs-*`):

1. **Logs de infraestructura**: el `otel-collector` lee `/var/lib/docker/containers/*/*.log` (el log driver `json-file` de Docker) de **todos** los contenedores del host — Postgres, Redis, RabbitMQ, Langflow, Langfuse, etc. — sin necesidad de instrumentarlos.
2. **Logs + traces de las apps propias**: `api` y los 4 workers están instrumentados con `opentelemetry-sdk` (ver `api_gateway/app/core/logging.py`), exportan por OTLP con `service.name` propio (`fd-gateway`, `fd-kafka-inbound-worker`, etc.), incluyendo `correlation_id` y ubicación en código (`code.file.path`/`line.number`). `n8n` (`fd-n8n`) y `evolution` también mandan sus propias trazas OTLP.

Para explorarlos: http://localhost:5601 (usuario `admin`, password `OPENSEARCH_PASSWORD`) → Discover → index pattern `ss4o_logs-*`.

> Nota multi-tenancy: OpenSearch Dashboards tiene tenants (Global/Private). Si no ves datos aunque el índice tenga documentos, revisá el selector de tenant arriba a la derecha — los index patterns quedan atados al tenant en el que estabas parado cuando los creaste.

### Trazas también en Langfuse (no solo OpenSearch)

El `otel-collector` reenvía **todo** lo que le llega por el pipeline `traces` a dos exporters a la vez: `opensearch` y `otlphttp/langfuse` (`otel-collector-config.yaml`). Este último le pega al endpoint OTLP público de Langfuse (`POST {LANGFUSE_BASE_URL}/api/public/otel/v1/traces`), autenticado con Basic Auth (`LANGFUSE_PUBLIC_KEY`:`LANGFUSE_SECRET_KEY` vía la extensión `basicauth/langfuse`).

- **Langflow** no pasa por acá — tiene su propio SDK de Langfuse nativo (`LANGFUSE_*` en el `environment` de `langflow`), con trazas ricas por componente (prompt, modelo, tokens).
- **n8n** sí pasa por el `otel-collector`: cada ejecución de workflow aparece en Langfuse como una traza `workflow.execute` (menos detallada que Langflow — no desglosa nodo por nodo). Verificado con `GET /api/public/traces` contra Langfuse después de disparar el workflow de la sección 13.
- Como el `otel-collector` solo corre en `profile prod` (sección 4), esta doble exportación (OpenSearch + Langfuse) también depende de ese profile.

---

## 15. Troubleshooting

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

### El pipeline completa (llega la respuesta por WS) pero dice "El workflow no devolvió una respuesta válida"

`LangflowExecutor` no está autenticando contra Langflow. Sin credenciales, `POST /api/v1/run/{flow_id}` no devuelve el error real: devuelve `200` con el HTML del frontend de Langflow (el flow cae en la ruta catch-all del SPA), así que `LangflowExecutor` lo toma como éxito y no encuentra ningún campo de texto reconocible.

Se soluciona con `LANGFLOW_API_KEY` (header `x-api-key`, ya lo manda `LangflowExecutor`) **y** que el flow no sea `PRIVATE` sin dueño:

```bash
# 1. Login como superuser (usuario/password "langflow" si nunca los cambiaste) y generar una API key real
TOKEN=$(curl -s -X POST http://localhost:7860/api/v1/login \
  -d "username=langflow&password=langflow" -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:7860/api/v1/api_key/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"flowsdone-gateway"}'
# → copiar "api_key" a LANGFLOW_API_KEY en .env, y recrear api + los 4 workers

# 2. Si el flow es uno de los templates de "Starter Projects" (sin dueño, access_type PRIVATE),
#    marcarlo PUBLIC para que /run acepte requests autenticados solo con la API key:
curl -s -X PATCH "http://localhost:7860/api/v1/flows/<flow_id>" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"access_type":"PUBLIC"}'
```

Si además no ves el flow al entrar a Langflow con ese usuario, es porque quedó en la carpeta de sistema "Starter Projects" (`user_id` nulo) en vez de en "My Projects" — movelo con `PATCH /api/v1/flows/<flow_id>` mandando el `folder_id` de tu carpeta (`GET /api/v1/folders/` para encontrarlo).

### Langfuse: "localhost ha rechazado la conexión"

Langfuse **no** escucha en el puerto por defecto de Next.js (`3000`) desde el host — ese es el puerto interno del contenedor. El puerto publicado es `LANGFUSE_PORT` (`.env`, por defecto `4100`). Entrá a `http://localhost:4100`, no a `:3000`.

### No veo trazas de n8n en Langfuse (ni en OpenSearch)

n8n 2.33.3 lee `N8N_OTEL_ENABLED` / `N8N_OTEL_EXPORTER_OTLP_ENDPOINT` — **no** `N8N_OTEL_TRACING_ENABLED`/`N8N_OTEL_TRACING_ENDPOINT`/`N8N_OTEL_TRACING_PROTOCOL` (nombres de una doc/versión vieja que esta versión ignora silenciosamente, sin error). Si tu `n8n` no manda nada, confirmá con `docker exec <n8n> printenv | grep OTEL` que las variables que ve el proceso son las correctas — ya están arregladas en `docker-compose.yml`, pero si algún override local las vuelve a poner mal, este es el síntoma (silencio total, ni logs de error).

### Langfuse crashea en loop / "JavaScript heap out of memory"

V8 necesita headroom bajo el límite del contenedor. No bajar `LANGFUSE_MEM_LIMIT`/`LANGFUSE_WORKER_MEM_LIMIT` de ~2560m, y mantener `NODE_OPTIONS=--max-old-space-size=2048` en el environment de `langfuse-web`.

### No llegan logs/traces al `otel-collector` desde otros contenedores

El receiver OTLP tiene que bindear explícitamente a `0.0.0.0` en `otel-collector-config.yaml` (`endpoint: 0.0.0.0:4317` / `:4318`). Si queda en el default (`localhost`), nada fuera del propio contenedor le puede pegar — el síntoma es `Failed to export logs batch due to timeout` en los logs de la app que intenta exportar.

### No veo nada en OpenSearch Dashboards aunque el índice tiene documentos

Revisá el tenant activo (selector arriba a la derecha, ícono de persona). Los index patterns creados vía API sin el header `securitytenant: global` quedan en el tenant "Private" del usuario que los creó, invisibles para otra sesión/tenant.

### Evolution API — error de autenticación en Prisma

Asegurate de usar `DATABASE_CONNECTION_URI` (no `DATABASE_URL`) en el environment del servicio — es lo que espera este fork.

### Un webhook de canal responde 200 pero el mensaje nunca llega a Langflow

Buscá en los logs de `api` `*.not_routable` (ej. `channels.whatsapp_evolution.not_routable`). Significa que no hay ningún `channel_connection` activo con ese `(channel_type, external_id)` — hay que crearlo primero vía `/internal/admin/channel-connections` (sección 8). El webhook devuelve `200` a propósito para que la plataforma de origen no reintente infinito por un problema de configuración nuestro.

### Traefik no rutea un dominio nuevo

Confirmá que agregaste el router **y** el service en `traefik-dynamic.yml` (no alcanza con la variable `DOMAIN_*` del `.env` — Traefik no la lee, ver sección 11).

---

## 16. Mantenimiento

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

---

## 17. Tests

Suite de tests unitarios con `pytest`, en `api_gateway/tests/`, mirroring la estructura de `api_gateway/app/`. No hay tests de integración todavía (nada pega contra Postgres/Kafka/RabbitMQ reales) — cada test mockea los puertos del dominio o la llamada HTTP saliente (`httpx.AsyncClient`), así que corren en milisegundos y no necesitan el stack levantado.

**Instalar y correr:**

```bash
# Dentro del contenedor (tiene el resto de las deps ya instaladas):
docker compose run --rm api sh -c "pip install -e '.[test]' && python -m pytest api_gateway/tests -q"

# O local, si tenés el venv del proyecto activado:
pip install -e ".[test]"
pytest
```

**Qué cubre:**

- `application/use_cases/` — los tres use cases de `channel_connections` (create/update/delete, con sus caminos de rollback), `IngestMessageUseCase`, `HandleOutboundResponseUseCase` (extracción de texto, callback, WS, entrega a canal nativo, registro del turno saliente en la Session — sección 20).
- `application/services/` — `register_or_compensate`, `WSRegistry` y `Switchboard` (sección 20: creación/reuso de Session, delegación al `AppConnectorPort` actual, `switch_app()`).
- `adapters/outbound/` — `RandomHexSecretGenerator`, `TelegramWebhookRegistrar`, `MetaWebhookRegistrar`, las dos factories (`ChannelSenderFactory`, `WebhookRegistrarFactory`), todos los senders (incluidos los stubs de X/TikTok), `RedisSessionRepository`, `LangflowAppConnector` y `AppConnectorFactory` (sección 20).
- `adapters/inbound/http/channels/` — los helpers puros de verificación de firma de cada canal (Meta, X, TikTok, extracción de texto de Evolution), más tests end-to-end vía ASGI (sin DB real, con fakes en `app.state`) para Telegram, Facebook y WhatsApp — los tres patrones de verificación distintos (secret por conexión, firma HMAC de app compartida, apikey estático).

**Qué falta (deliberadamente fuera de este alcance):** tests end-to-end de Instagram/X/TikTok a nivel HTTP (sus helpers de firma sí están cubiertos), y cualquier test de integración contra Postgres/Kafka/RabbitMQ reales o contra el `admin` router completo (routers CRUD), `adapters/outbound/db/` (repositorios SQLAlchemy), `infrastructure/` o `main.py` (wiring de arranque). Los fakes reutilizables viven en `tests/support/` (`fakes.py` para los puertos, `fake_httpx.py` para las llamadas salientes, `asgi.py` para levantar un router aislado).

### Cobertura

`pytest-cov` mide cobertura sobre `app` (config en `[tool.coverage.*]` de `pyproject.toml`):

```bash
docker compose run --rm api sh -c "pip install -e '.[test]' && python -m pytest --cov --cov-report=term-missing"
```

Hoy da ~69% total, pero es un número engañoso si se lee suelto: `application/` y la mayor parte de `adapters/` están arriba del 90-100%, mientras que `admin/`, `adapters/outbound/db/`, `infrastructure/` y `main.py` están en 0% (no son parte de esta suite todavía, ver arriba). `fail_under = 65` en `pyproject.toml` es un **piso inicial**, no una meta — dejar margen bajo el actual evita que el gate rompa por fluctuaciones menores, pero la idea es subirlo a medida que se sumen tests a esas capas, nunca bajarlo para acomodar código nuevo sin cubrir.

### CI

`.github/workflows/deploy.yml` tiene dos triggers (`push` a `main` y `pull_request` contra `main`) y dos jobs:

- **`test`** corre en ambos casos: en cada PR (para tener feedback antes de mergear — si querés que bloquee el botón de "Merge", hay que activar branch protection con este check como obligatorio, no viene forzado por el workflow en sí) y de nuevo en el push a `main` tras el merge. Corre en un runner de GitHub limpio (no en el stack de `docker-compose`), con `--cov` respetando el `fail_under` de `pyproject.toml`.
- **`deploy`** solo corre en el evento `push` (`if: github.event_name == 'push'`) y depende de `test` (`needs: test`) — nunca se dispara desde una PR (evitaría deployar código sin mergear al VPS), y si los tests o la cobertura fallan en el push a `main`, no llega a pegarle por SSH al servidor.

---

## 18. Canal de voz (Twilio ConversationRelay)

Transforma la plataforma de agentes en un voicebot telefónico: alguien llama a un número de Twilio, y el mismo agente de Langflow que responde por WhatsApp/Telegram/webchat le contesta por voz. Sigue la arquitectura hexagonal del resto del proyecto — módulo aislado dentro de `api_gateway`, no un microservicio separado (aunque queda desacoplado por puertos + topic propio como para poder extraerlo más adelante sin reescribir lógica).

**Cómo funciona (Twilio ConversationRelay, no Media Streams crudo):** Twilio hace el STT/TTS por su cuenta. Nuestro backend nunca toca audio — recibe/envía **texto** por un WebSocket, exactamente como cualquier otro canal de texto en tiempo real. El "cerebro" sigue siendo 100% Langflow; Twilio es puro transporte de voz, tan "tonto" como Evolution API lo es para WhatsApp.

```
Llamada entrante
   │ POST /webhooks/voice  (TwiML — sin "twilio" en la ruta, a propósito)
   ▼
api ── resuelve ChannelConnection(channel_type="voice") + ChannelApp("twilio")
   │   ── verifica X-Twilio-Signature
   │   ── guarda la sesión de la llamada en Redis (TTL)
   │   ── responde TwiML: <Connect><ConversationRelay url="wss://.../voice/stream/{call_sid}"/></Connect>
   ▼
Twilio abre WS a /voice/stream/{call_sid}  (frames: setup / prompt / interrupt / dtmf / end)
   ▼
api (WS) ── por cada "prompt" (turno transcrito) → mismo Switchboard.handle_inbound_turn()
   │         que usan los demás canales (sección 20); LangflowAppConnector infiere
   │         transport="kafka_voice" solo por channel_type="voice", sin caso especial en el WS
   ▼
Kafka: VOICE_KAFKA_TOPIC ("voice.messages") — topic propio, separado de inbound.messages
   ▼
kafka_voice_worker ── ExecuteWorkflowUseCase (Langflow, mismo flow que ya usás en otros canales)
   │                 ── POST /internal/outbound (HMAC) — el mismo endpoint genérico que ya
   │                    usan kafka_outbound_worker/rabbitmq_outbound_worker, sin ruta nueva
   ▼
api ── TwilioVoiceSender empuja la respuesta al WebSocket abierto → Twilio la dice en voz alta
```

Por qué es **un solo worker** y no un par inbound/outbound como el resto de los canales: el topic propio (`VOICE_KAFKA_TOPIC`) ya aísla la voz de los demás canales, que es lo que de verdad importa; republicar la propia respuesta a Kafka para que otro worker la vuelva a consumir sería una vuelta extra sin beneficio.

### Puesta en marcha

```bash
KEY="$ADMIN_API_KEY"

# 1. Migración (channel_type "voice" + provider "twilio")
docker compose run --rm api alembic -c api_gateway/alembic.ini upgrade head

# 2. App compartida de Twilio (Account SID + Auth Token, una sola para todo el SaaS —
#    mismo modelo que Meta/X/TikTok en la sección 9)
curl -s -X PUT http://localhost:8000/internal/admin/channel-apps/twilio \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"credentials": {"account_sid": "AC...", "auth_token": "..."}}'

# 3. Conexión del número (el número específico, como la instance de Evolution o el bot_token
#    de Telegram). `config.provider` es quién implementa VoiceProviderPort para este número —
#    hoy solo "twilio", pero deja la puerta abierta a otro proveedor de voz sin tocar el resto.
curl -s -X POST http://localhost:8000/internal/admin/channel-connections \
  -H "X-Admin-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
        "project_id":"<project_id>",
        "agent_id":"<agent_id>",
        "channel_type":"voice",
        "external_id":"+1XXXXXXXXXX",
        "config":{"provider":"twilio"}
      }'

# 4. En la consola de Twilio (o vía API), configurar el Voice Webhook del número:
#    https://<PUBLIC_BASE_URL>/webhooks/voice  (POST)
```

`config` acepta más claves opcionales, sin volver a tocar código: `voice`/`tts_provider` (personalizar la voz TTS, ver más abajo) y `human_transfer_number`/`human_transfer_phrases` (transferencia a un agente humano, ver más abajo).

### Diseño: por qué el webhook no identifica al proveedor

Ni `/webhooks/voice` ni `wss://.../voice/stream/{call_sid}` mencionan "twilio" en la ruta — deliberado. Internamente sí se modela quién es el proveedor (`ChannelConnection.config.provider`, `ChannelApp.provider`), pero nunca se expone en una URL pública. Dos razones:

- Si mañana se suma otro proveedor de voz, la URL pública no cambia — solo se agrega una implementación más de `VoiceProviderPort` (Strategy: firma, TwiML, parseo de frames), sin tocar routers ni casos de uso.
- No revela en la superficie pública qué tecnología corre detrás.

### Variables de entorno nuevas

| Variable | Para qué |
|---|---|
| `VOICE_KAFKA_TOPIC` | Topic Kafka dedicado a voz (default `voice.messages`), separado de `KAFKA_TOPIC` |
| `VOICE_KAFKA_TOPIC_PARTITIONS` | Particiones de `VOICE_KAFKA_TOPIC` (default `3`) |
| `KAFKA_VOICE_WORKER_MEM_LIMIT` / `_CPUS` | Límites de recursos del contenedor `kafka_voice_worker` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Conexión a Redis para `CallSessionRepositoryPort` (estado efímero de la llamada entre el webhook TwiML y el WebSocket, que llegan como dos requests separados) — reusa los mismos valores que ya usa el resto del stack |
| `CALL_SESSION_TTL_SECONDS` | TTL de la sesión de llamada en Redis (default `7200`), cota superior de duración de una llamada |

No hay `TWILIO_ACCOUNT_SID`/`AUTH_TOKEN` en `.env`: siguiendo el mismo patrón que Meta/X/TikTok (sección 9), esas credenciales viven exclusivamente en `channel_apps`/`channel_connections` vía el admin API, nunca en variables de entorno.

### Personalizar la voz (TTS) por número

`ChannelConnection.config` acepta `voice`/`tts_provider`/`language`, que se pasan directo como atributos del TwiML `<ConversationRelay>` — cambiarla es un `PATCH`, sin recrear nada:

```bash
curl -X PATCH http://localhost:8000/internal/admin/channel-connections/<id> \
  -H "X-Admin-Api-Key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"config": {"provider": "twilio", "tts_provider": "Amazon", "voice": "Polly.Mia-Neural"}}'
```

⚠️ **No mandes `language` salvo que también configures transcripción (STT).** Twilio trata `language` como un set todo-o-nada: si lo definís, exige que `transcriptionProvider`/`speechModel` también estén presentes, o rechaza la llamada entera con el error [64101](https://www.twilio.com/docs/errors/64101) ("Incomplete value set..."), que se manifiesta como una llamada que corta sola con un mensaje en inglés que Twilio inyecta. Para solo cambiar la voz/acento, alcanza con `voice` + `tts_provider`.

### Transferencia a un agente humano ("handoff")

Requisito legal habitual: siempre ofrecer la opción de hablar con una persona. Se implementa con el mecanismo de **handoff** de ConversationRelay — no es la app la que controla la llamada telefónica directamente, sino que le devolvemos el control a Twilio para que haga un `<Dial>` a otro número:

```
Caller dice una frase de transferencia (config)
   ▼
api (WS /voice/stream/{call_sid}) ── detecta la frase (determinístico, NO depende del LLM)
   │                               ── NO enruta ese turno a Langflow/Kafka
   │                               ── manda {"type":"end","handoffData":"{...}"} por el WS
   ▼
Twilio termina ConversationRelay y hace un nuevo POST a la action_url del <Connect> original
   ▼
api (POST /webhooks/voice/handoff) ── verifica firma, lee handoffData, responde <Dial>+34...</Dial>
   ▼
Twilio bridgea la llamada al número humano
```

La detección de frases es **determinística** (substring, case-insensitive, `stream.py:_matches_human_transfer_phrase`) y corre antes de tocar Langflow — a propósito, para que el cumplimiento legal no dependa de que el LLM interprete bien la intención.

Configuración por conexión (mismo mecanismo que la voz — `ChannelConnection.config`):

```bash
curl -X PATCH http://localhost:8000/internal/admin/channel-connections/<id> \
  -H "X-Admin-Api-Key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{
        "config": {
          "provider": "twilio",
          "human_transfer_number": "+34601491522",
          "human_transfer_phrases": ["hablar con una persona", "agente humano", "quiero un operador"]
        }
      }'
```

Si `human_transfer_number` no está configurado, el `<Connect>` inicial no lleva `action` y esta feature queda desactivada para esa conexión (sin costo de webhook extra). No hay matching difuso ni normalización de acentos todavía — ver limitaciones.

### Limitaciones conocidas (documentadas, no resueltas todavía)

- **Una sola partición efectiva por ahora:** `IngestMessageUseCase` particiona por `key=channel` (igual que los demás canales), así que hoy todas las llamadas de voz caen en la misma partición de `VOICE_KAFKA_TOPIC` — no hay paralelismo real entre llamadas concurrentes. Con el volumen inicial no es un problema; si crece, hace falta particionar por `call_sid`, lo que implica generalizar la partition-key strategy de `IngestMessageUseCase` (afecta también a los canales de texto, por eso se dejó fuera de esta feature).
- **DLQ de `VOICE_KAFKA_TOPIC` no implementada** — mismo estado que `DLQ_TOPIC` del resto del gateway (el topic se crea pero nada publica ahí todavía).
- **Sin eventos de control de llamada** (call_started/ended, DTMF) como topic/analítica separada — queda para una iteración futura si hace falta.
- **Detección de frases de transferencia sin normalización** — substring plano en minúsculas, sin manejo de acentos/tildes ni fuzzy matching. Si el STT transcribe "quiero hablar con una persona" con alguna variación no cubierta en `human_transfer_phrases`, no dispara. Complementarlo con detección por DTMF ("marcar 0") es una opción más robusta, no implementada todavía.

---

## 19. Softphone de prueba (demo)

Herramienta de dev/testing — **no** es parte del canal de voz de producción (sección 18). Deja llamar por WebRTC (Twilio Voice JS SDK) desde el navegador al mismo `/webhooks/voice` que usa una llamada real, sin gastar minutos ni necesitar un teléfono. Vive en `static/voice_demo/`, mismo patrón que el widget de webchat (`static/webchat/`, sección 10).

El TwiML App que usa el softphone apunta su Voice Request URL al mismo `/webhooks/voice` de siempre — no hay lógica de backend nueva para la llamada en sí, solo un endpoint que emite el Access Token que el SDK necesita para autenticar al navegador contra Twilio (`GET /voice-demo/token`, `adapters/inbound/http/voice_demo.py`).

### Puesta en marcha

```bash
# 1. Crear la API Key y el TwiML App en Twilio (una sola vez), usando el Account SID/
#    Auth Token ya guardados como ChannelApp "twilio" (sección 18):
uv run python -c "
from twilio.rest import Client
client = Client('<account_sid>', '<auth_token>')
app = client.applications.create(
    friendly_name='Flowsdone Voice Demo Softphone',
    voice_url='<PUBLIC_BASE_URL>/webhooks/voice', voice_method='POST',
)
key = client.new_keys.create(friendly_name='voice-demo-softphone')
print('TWIML_APP_SID=' + app.sid)
print('API_KEY_SID=' + key.sid)
print('API_KEY_SECRET=' + key.secret)
"

# 2. Completar en .env: VOICE_DEMO_TWILIO_ACCOUNT_SID/_API_KEY_SID/_API_KEY_SECRET/_TWIML_APP_SID
#    (ver env.example.txt para el detalle de cada una)

# 3. Recrear api y abrir en el navegador
docker compose up -d --force-recreate api
```

Luego abrí `http://localhost:8000/static/voice_demo/index.html?to=+1XXXXXXXXXX` (o el dominio público) — pide permiso de micrófono, y el botón "Llamar" dispara `device.connect({params: {To: "+1XXXXXXXXXX"}})`, que Twilio traduce en una request a `/webhooks/voice` con `To=+1XXXXXXXXXX` y `From=client:<identity>` — el mismo webhook de siempre, sin cambios.

### Exponer el stack local a internet (`scripts/dev/voice_demo_tunnel.sh`)

Para que el softphone funcione, **Twilio** (no tu navegador) tiene que poder alcanzar `/webhooks/voice` — si estás probando en un entorno sin dominio público real, hace falta un túnel. El script automatiza todo con [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) (quick tunnel, sin cuenta ni dominio propio):

```bash
scripts/dev/voice_demo_tunnel.sh start
# - Descarga cloudflared si hace falta (scripts/dev/cloudflared, gitignored)
# - Levanta el túnel y captura la URL pública (https://xxxx.trycloudflare.com)
# - Sobreescribe PUBLIC_BASE_URL en .env con esa URL y recrea el contenedor api
# - Apunta el TwiML App de Twilio (VOICE_DEMO_TWILIO_TWIML_APP_SID) a esa URL
# - Imprime el link del softphone listo para abrir

scripts/dev/voice_demo_tunnel.sh stop
# Revierte PUBLIC_BASE_URL al valor original y recrea api
```

⚠️ Mientras el túnel está activo, `PUBLIC_BASE_URL` en `.env` **no** es el dominio real — no confundir con un problema de DNS/Traefik si `platform.flowsdone.com` deja de responder como esperás durante una sesión de pruebas. Correr `stop` antes de volver a tocar producción.

---

## 20. Switchboard + Session (centralita de conmutación)

Hasta esta feature, todo mensaje entrante de cualquier canal iba **siempre** a Langflow: `RouteChannelMessageUseCase` resolvía `(channel_type, external_id)` → tenant/proyecto/agente y publicaba en Kafka en cada turno, sin ningún estado de conversación persistido entre turnos. `Switchboard` (`application/services/switchboard.py`) reemplaza ese use case como **punto único de entrada** para los 8 canales (Facebook, Instagram, WhatsApp, Telegram, X, TikTok, voz — y webchat sigue aparte, ver más abajo), y agrega lo que faltaba: una `Session` persistida que sabe qué "app" está atendiendo la conversación en este momento, para poder conmutarla en el futuro hacia otros destinos (un sistema de tickets externo, otro bot, correo) sin reescribir el pipeline de canales.

Esta feature construye la **infraestructura** de conmutación (`Switchboard.switch_app()`, ya funcional) pero deliberadamente **no** incluye ningún motor de reglas/frases que la dispare automáticamente — hoy `current_app` siempre arranca en `"langflow"` y solo cambia si algo externo llama a `switch_app()` explícitamente (no hay endpoint HTTP para eso todavía, tampoco: se agrega junto con el primer conector real).

### Dos "sesiones" conviven en voz, a propósito

`CallSession` (Redis, sección 18) resuelve un problema distinto: puente de estado entre el webhook TwiML y el WebSocket de streaming de **una llamada**, de vida corta (TTL `CALL_SESSION_TTL_SECONDS`). La nueva `Session` resuelve el estado conversacional de **toda la plataforma**, de vida larga (TTL `SESSION_TTL_SECONDS`, 24h por defecto). No se fusionan — `voice/stream.py` sigue usando `CallSession` para lo que ya resuelve bien, y además pasa por `Switchboard.handle_inbound_turn()` igual que cualquier otro canal para decidir qué app atiende el turno.

### Flujo

```
Webhook de canal (Facebook/Instagram/WhatsApp/Telegram/X/TikTok/voz)
   │
   ▼
Switchboard.handle_inbound_turn(channel_type, external_id, external_conversation_key,
                                 sender_id, message_text, raw_payload)
   │
   ├─ session_id = f"{project_id}:{channel_type}:{external_conversation_key}"
   │  (mismo formato de siempre — Langflow sigue recibiendo el mismo session_id/
   │   conversation_id, así que su memoria de conversación no se ve afectada)
   │
   ├─ session_repo.get(session_id)  (Redis)
   │  si no existe: channel_connection_repo.get_by_channel_and_external_id(...) resuelve
   │  tenant/proyecto/agente (igual que antes), crea la Session con current_app="langflow"
   │  y session.variables["langflow_flow_id"] = <flow_id resuelto AHORA, snapshot único>
   │
   ├─ app_connectors[session.current_app].handle_turn(session, message_text, raw_payload)
   │  (Strategy — hoy solo existe "langflow": LangflowAppConnector, que dispara
   │  IngestMessageUseCase igual que siempre, con transport="kafka_voice" si
   │  channel_type=="voice" o "kafka" para cualquier otro canal; devuelve None,
   │  la respuesta llega después por el pipeline Kafka+Langflow de siempre)
   │
   ├─ registra el turno entrante en Postgres (session_messages) y en la ventana
   │  corta de la Session (últimos 10 mensajes), guarda la Session en Redis
   │
   └─ si el conector devolvió una respuesta síncrona (ningún conector la devuelve
      hoy, pero el contrato ya lo soporta) → Switchboard la entrega inmediatamente
      reusando HandleOutboundResponseUseCase.deliver(), sin duplicar lógica de envío

HandleOutboundResponseUseCase.deliver()  (llamado por /internal/outbound, sin cambio
   de responsabilidad — solo gana un paso extra al final de una entrega exitosa)
   │
   └─ registra el turno saliente en Postgres (session_messages) y actualiza la
      Session en Redis (best-effort: nunca rompe una entrega ya exitosa)
```

**Por qué el flow_id de Langflow se snapshotea una sola vez:** antes de esta feature, `RouteChannelMessageUseCase` releía `agent.langflow_flow_id` en cada turno — si un admin cambiaba el flow del agente a mitad de una conversación, el siguiente turno silenciosamente empezaba a hablar con otro flow, sin que nadie lo pidiera. Ahora ese valor se resuelve una única vez, al crear la `Session`, y queda fijo en `session.variables["langflow_flow_id"]` para toda la conversación.

**Webchat no pasa por Switchboard** — sigue yendo directo por WebSocket a `IngestMessageUseCase` como siempre (no tiene `channel_connection`, no hay nada que resolver). No tiene `Session`; `HandleOutboundResponseUseCase` detecta la ausencia de `channel_connection_id` y no intenta registrar historial.

### Piezas nuevas

| Pieza | Dónde | Qué hace |
|---|---|---|
| `Session` / `SessionMessage` | `domain/models/session.py` | Estado de la conversación: canal, `current_app`, `variables`, últimos 10 mensajes, `started_at`/`last_activity_at`. |
| `SessionRepositoryPort` → `RedisSessionRepository` | `domain/ports/outbound/`, `adapters/outbound/session/` | Lectura/escritura rápida con TTL (`SESSION_TTL_SECONDS`), mismo patrón que `CallSessionRepositoryPort`. |
| `SessionHistoryRepositoryPort` → `PostgresSessionHistoryRepository` | ídem | Histórico durable turno-a-turno (`session_messages`) y de eventos (`session_events`: `started`/`app_switched`/`closed`) — migración `0004_switchboard_sessions`. |
| `AppConnectorPort` (Strategy) → `LangflowAppConnector` | `domain/ports/outbound/app_connector.py`, `adapters/outbound/apps/` | Contrato para cualquier "app" destino. Hoy solo Langflow está implementado; un ticketing system/otro bot/email futuro implementan el mismo puerto sin tocar `Switchboard`. |
| `Switchboard` | `application/services/switchboard.py` | Resuelve/crea la `Session`, delega al conector actual, registra historial, expone `switch_app(session_id, to_app, reason=None)`. |

### Variables de entorno nuevas

| Variable | Para qué |
|---|---|
| `SESSION_TTL_SECONDS` | TTL de la `Session` en Redis (default `86400`, 24h) — mucho más largo que `CALL_SESSION_TTL_SECONDS` porque una conversación de WhatsApp/Telegram puede retomarse horas después y debe seguir contando como la misma sesión. |

### Fuera de alcance (a propósito, por ahora)

- Conectores reales para Zendesk/Jira/Salesforce/email/otro bot — solo existe `LangflowAppConnector`.
- Endpoint HTTP para invocar `switch_app()` — no tiene sentido exponerlo con un solo conector registrado; llega junto con el segundo.
- Cualquier motor de disparo automático de conmutación (por frase, por intención, por regla) — esta feature es solo la infraestructura de conmutación, no el "cuándo".

