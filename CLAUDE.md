# Proyecto: Flowsdone_Ecosystem

Plataforma de servicios de IA generativa: workflows automatizados, orquestación de agentes, mensajería en tiempo real e integraciones (WhatsApp/Evolution API, webchat propio). Stack desplegado con Docker Compose sobre Ubuntu (Docker Engine nativo, no Docker Desktop).

## Arquitectura
Hexagonal (Ports & Adapters). Separación estricta entre dominio, aplicación e infraestructura.

- El **dominio** no conoce frameworks, ni DB, ni colas, ni Langflow. Solo modelos y puertos (interfaces).
- La **aplicación** orquesta casos de uso combinando puertos, sin saber cómo se implementan.
- Los **adaptadores** son la única capa que toca tecnología concreta (HTTP, Kafka, Postgres, Langflow, etc.).
- Las dependencias siempre apuntan hacia el dominio, nunca al revés.

## Stack técnico

**Backend**
- Python (FastAPI/async)
- WebSockets para comunicación en tiempo real (webchat gateway propio)

**Mensajería / eventos**
- Kafka — eventos de dominio, streaming
- RabbitMQ — colas de trabajo / tareas puntuales

**IA / Orquestación**
- Langflow — ejecución de workflows de IA
- n8n — automatizaciones y orquestación de procesos
- Langfuse — observabilidad y tracing de LLMs
- Weaviate — vector store / búsqueda semántica

**Datos**
- PostgreSQL — persistencia transaccional (con idempotencia)
- Redis — caché / estado efímero
- ClickHouse — analítica y eventos de alto volumen
- OpenSearch — búsqueda / logs

**Integraciones**
- Evolution API — integración con WhatsApp

**Infraestructura**
- Docker Compose (stack completo autogestionado en VPS Linux)
- GitHub Actions — CI/CD, despliegue automático en VPS al hacer merge a main
- Gestión cuidadosa de secretos: nunca credenciales en el repo ni en `.env` versionado (ver sección "Seguridad")

## Estructura clave
- `domain/` → modelos y puertos (interfaces puras, sin dependencias externas)
- `application/` → casos de uso y DTOs
- `adapters/inbound/` → HTTP, WebSocket, colas de entrada (consumers de Kafka/RabbitMQ)
- `adapters/outbound/` → DB, HTTP externo, Langflow, Evolution API, colas de salida (producers)
- `infrastructure/` → implementaciones técnicas (config de DB, administración de Kafka, clientes de Weaviate/Langfuse)
- `core/` → config, logging, middleware, utils

## Convenciones
- Los puertos se definen en `domain/ports/` como interfaces (Protocol/ABC)
- Los adaptadores implementan los puertos, nunca al revés
- Los casos de uso en `application/use_cases/` orquestan la lógica, sin lógica de infraestructura
- Los eventos de dominio (Kafka) llevan un identificador único para garantizar idempotencia en consumidores
- Cada servicio del `docker-compose.yml` debe tener healthcheck definido
- Variables sensibles solo en `.env` (nunca commiteado); usar `.env.example` como plantilla

## Lo que NO hacer
- No importar adaptadores desde el dominio
- No lógica de negocio en adaptadores
- No exponer clientes de infraestructura (Kafka, Langflow, DB) directamente en `application/`; siempre a través de un puerto
- No commitear `.env`, claves de API (OpenAI, Evolution API, etc.) ni secretos de ningún tipo
- No acoplar `application/` a un adaptador concreto (p. ej. asumir que el vector store siempre será Weaviate)

## Seguridad
- Si una credencial se filtra accidentalmente en el historial de Git, requiere reescritura completa del historial + force-push (ya ha ocurrido una vez con una API key de OpenAI)
- Revisar `.gitignore` incluye `.env`, `*.env.local` y cualquier archivo de credenciales antes de cada commit importante
- Rotar la credencial expuesta inmediatamente, no solo eliminarla del historial

## Despliegue
- Push/merge a `main` → GitHub Actions dispara despliegue automático al VPS
- El VPS ejecuta el stack completo vía Docker Compose
- Verificar healthchecks de todos los servicios tras cada despliegue antes de dar por bueno el release

## Flujo de trabajo (obligatorio para cada tarea)

Cada vez que se aborde una nueva tarea, seguir GitFlow sin excepción:

1. **Crear rama desde `develop`** (nunca trabajar directo sobre `main` ni `develop`):
   - `feature/<nombre-tarea>` → nuevas funcionalidades
   - `fix/<nombre-tarea>` → corrección de bugs
   - `hotfix/<nombre-tarea>` → parches urgentes sobre `main`
   - `release/<version>` → preparación de release
2. **Antes de subir cualquier commit final de la tarea**:
   - Generar/actualizar **docstrings** en todas las funciones, clases y métodos públicos tocados (formato Google o NumPy, consistente con el resto del módulo)
   - Generar/actualizar **tests** (unitarios como mínimo; de integración si la tarea toca un adaptador) cubriendo el caso de uso o comportamiento nuevo
   - Ejecutar la suite de tests localmente y confirmar que pasa antes de hacer push
3. **Al terminar la tarea**:
   - Hacer push de la rama al remoto
   - **Antes de generar el link de la PR, preguntar siempre si hay algún otro requerimiento pendiente** (cambios adicionales, ajustes, algo que revisar) y esperar confirmación antes de continuar
   - Una vez confirmado que no hay más requerimientos, preparar y generar el **link de la Pull Request** (rama origen → `develop`, o → `main` si es `hotfix`), con:
     - Título descriptivo de la tarea
     - Resumen de los cambios
     - Referencia al issue/tarea si existe
     - Checklist de que docstrings y tests están incluidos
- No se considera una tarea terminada si falta cualquiera de los tres puntos anteriores (docstrings, tests, PR generada)