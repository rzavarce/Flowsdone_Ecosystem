# Proyecto: [nombre de tu app]

## Arquitectura
Hexagonal (Ports & Adapters). Separación estricta entre dominio, aplicación e infraestructura.

## Stack
- Python (FastAPI/async)
- Kafka y RabbitMQ (mensajería)
- Langflow (ejecución de workflows IA)
- WebSockets (comunicación en tiempo real)
- Base de datos con idempotencia

## Estructura clave
- `domain/` → modelos y puertos (interfaces puras, sin dependencias externas)
- `application/` → casos de uso y DTOs
- `adapters/inbound/` → HTTP, WebSocket, colas de entrada
- `adapters/outbound/` → DB, HTTP externo, Langflow, colas de salida
- `infrastructure/` → implementaciones técnicas (DB, Kafka admin)
- `core/` → config, logging, middleware, utils

## Convenciones
- Los puertos se definen en `domain/ports/`
- Los adaptadores implementan los puertos, nunca al revés
- Los casos de uso en `application/use_cases/` orquestan la lógica

## Lo que NO hacer
- No importar adaptadores desde el dominio
- No lógica de negocio en adaptadores