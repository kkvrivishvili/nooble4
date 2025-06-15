# Estándar de Colas Redis en Nooble4

> **Última Revisión:** 15 de Junio de 2025
> **Estado:** Actualizado para reflejar el uso de Redis Streams para acciones.
> **Clase de Referencia:** `common.clients.QueueManager`

## 1. Introducción

Este documento establece el estándar para la nomenclatura de **Streams y Colas de Redis** en Nooble4. Con la adopción de Redis Streams para la comunicación principal de `DomainAction`s, es crucial distinguir entre:
- **Redis Streams**: Usados por los `BaseWorker`s para consumir `DomainAction`s de manera escalable (con consumer groups) y por `BaseRedisClient` para enviar dichas acciones (`XADD`).
- **Colas Redis (Listas)**: Usadas por `BaseRedisClient` para patrones de respuesta pseudo-síncrona y callbacks asíncronos, donde se espera un `DomainActionResponse` o un `DomainAction` de callback en una lista específica (consumida con `BLPOP` o similar).

El objetivo sigue siendo simple: **nadie debe construir nombres de streams o colas manualmente**. Toda la lógica de nomenclatura está centralizada en la clase `QueueManager`.

## 2. El `QueueManager`: La Única Fuente de Verdad

La clase `QueueManager`, ubicada en `common/clients/queue_manager.py`, es la responsable de generar todos los nombres de colas de manera consistente y predecible. 

Se inicializa con:
- `prefix`: El prefijo global para todas las claves (por defecto "nooble4").
- `environment`: El entorno de despliegue (ej. "dev", "prod"), obtenido de `CommonAppSettings` o la variable de entorno `ENVIRONMENT`.

El `service_name` y otros parámetros contextuales se pasan a los métodos específicos del `QueueManager` según sea necesario.

### 2.1. Uso en Componentes Base

- **`BaseWorker`**: Utiliza `QueueManager` para obtener el nombre del **Stream de Acciones** del cual consumirá mensajes usando un consumer group.
- **`BaseRedisClient`**: Utiliza `QueueManager` para:
    - Obtener el nombre del **Stream de Acciones** al cual enviará `DomainAction`s (usando `XADD`).
    - Obtener nombres de **Colas de Respuesta** (listas) para el patrón pseudo-síncrono.
    - Obtener nombres de **Colas de Callback** (listas) para el patrón asíncrono con callback.

Esto garantiza que el servicio que envía un mensaje y el que lo recibe usen exactamente la misma convención para nombrar el stream o la cola, abstrayendo esta complejidad.

## 3. Formato de las Colas Generadas

Aunque los desarrolladores no necesitan construir estos nombres, es útil conocer el patrón para fines de depuración y monitoreo en Redis.

### a) Streams de Acciones

Son los **Redis Streams** donde los workers (`BaseWorker`) escuchan por nuevas `DomainAction`s. Los workers operan como parte de un **consumer group** sobre estos streams para permitir el procesamiento distribuido y la gestión de mensajes (ACKs, mensajes pendientes).

*   **Método en `QueueManager`**: `get_action_stream_name(service_name: str, context: Optional[str] = None)`
*   **Formato del Stream**: `{prefix}:{env}:{service_name}[:{context}]:actions:stream` (se añade `:stream` para diferenciarlo explícitamente si fuera necesario, aunque el método ya lo indica)
*   **Ejemplos**:
    *   `nooble4:dev:embedding:actions:stream`
    *   `nooble4:dev:agent_execution:tenant_123:actions:stream`

_Nota: El nombre del consumer group utilizado por `BaseWorker` también se deriva de esta información, típicamente añadiendo un sufijo como `_group` al nombre base del stream o al nombre del servicio._

### b) Colas de Respuesta (Pseudo-Síncronas) - Listas Redis

Son **colas Redis tradicionales (listas)** temporales creadas y escuchadas (usando `BLPOP` o similar) por `BaseRedisClient` para cada llamada pseudo-síncrona, esperando una `DomainActionResponse`.

*   **Método en `QueueManager`**: `get_response_queue(origin_service: str, action_name: str, correlation_id: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:responses:{action_name}:{correlation_id}`
*   **Ejemplo**: `nooble4:dev:orchestrator:responses:agent.run_tool:a1b2c3d4`

### c) Colas de Callback (Asíncronas) - Listas Redis

Para flujos asíncronos donde un servicio solicitante espera una notificación/respuesta (`DomainAction` de callback) posterior en una **cola Redis tradicional (lista)** específica.

*   **Método en `QueueManager`**: `get_callback_queue(origin_service: str, event_name: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:callbacks:{event_name}`
*   **Ejemplo**: `nooble4:dev:ingestion:doc_xyz:callbacks:embedding_completed`

### d) Canales de Notificación (Pub/Sub)

Para patrones de publicación/suscripción.

*   **Método en `QueueManager`**: `get_notification_channel(origin_service: str, event_name: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:notifications:{event_name}`
*   **Ejemplo**: `nooble4:dev:document_service:notifications:document_updated`

## 4. Conclusión

La estandarización de la nomenclatura para **Streams y Colas (Listas)** se logra mediante la **centralización de la lógica en `QueueManager`**. Al utilizar `BaseWorker` (para consumir de streams) y `BaseRedisClient` (para enviar a streams y gestionar colas de respuesta/callback), los servicios se adhieren automáticamente al estándar. El rol del desarrollador es entender los patrones de comunicación (`send_action_pseudo_sync`, `send_action_async_with_callback`, `send_action_async` a streams) y los parámetros que estos requieren, confiando en que la infraestructura de comunicación subyacente está gestionada correctamente por los componentes base.
