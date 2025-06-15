# Estándar de Colas Redis en Nooble4

> **Última Revisión:** 14 de Junio de 2025
> **Estado:** Actualizado según implementación vigente.
> **Clase de Referencia:** `common.clients.QueueManager`

## 1. Introducción

Este documento establece el estándar para la nomenclatura de colas Redis en Nooble4. El objetivo es simple: **nadie debe construir nombres de colas manualmente**. Toda la lógica de nomenclatura está centralizada en la clase `QueueManager`.

## 2. El `QueueManager`: La Única Fuente de Verdad

La clase `QueueManager`, ubicada en `common/clients/queue_manager.py`, es la responsable de generar todos los nombres de colas de manera consistente y predecible. 

Se inicializa con:
- `prefix`: El prefijo global para todas las claves (por defecto "nooble4").
- `environment`: El entorno de despliegue (ej. "dev", "prod"), obtenido de `CommonAppSettings` o la variable de entorno `ENVIRONMENT`.

El `service_name` y otros parámetros contextuales se pasan a los métodos específicos del `QueueManager` según sea necesario.

### 2.1. Uso en Componentes Base

Tanto `BaseWorker` (para escuchar) como `BaseRedisClient` (para enviar) utilizan una instancia de `QueueManager` internamente. Esto garantiza que el servicio que envía un mensaje y el que lo recibe usen exactamente la misma convención para nombrar la cola, abstrayendo esta complejidad del desarrollador del servicio.

## 3. Formato de las Colas Generadas

Aunque los desarrolladores no necesitan construir estos nombres, es útil conocer el patrón para fines de depuración y monitoreo en Redis.

### a) Colas de Acciones

Son las colas donde los workers (`BaseWorker`) escuchan por trabajo nuevo.

*   **Método en `QueueManager`**: `get_action_queue(service_name: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{service_name}[:{context}]:actions`
*   **Ejemplos**:
    *   `nooble4:dev:embedding:actions`
    *   `nooble4:dev:agent_execution:tenant_123:actions`

### b) Colas de Respuesta (Pseudo-Síncronas)

Son colas temporales creadas y escuchadas por `BaseRedisClient` para cada llamada pseudo-síncrona, esperando una `DomainActionResponse`.

*   **Método en `QueueManager`**: `get_response_queue(origin_service: str, action_name: str, correlation_id: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:responses:{action_name}:{correlation_id}`
*   **Ejemplo**: `nooble4:dev:orchestrator:responses:agent.run_tool:a1b2c3d4`

### c) Colas de Callback (Asíncronas)

Para flujos asíncronos donde un servicio solicitante espera una notificación/respuesta posterior en una cola específica.

*   **Método en `QueueManager`**: `get_callback_queue(origin_service: str, event_name: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:callbacks:{event_name}`
*   **Ejemplo**: `nooble4:dev:ingestion:doc_xyz:callbacks:embedding_completed`

### d) Canales de Notificación (Pub/Sub)

Para patrones de publicación/suscripción.

*   **Método en `QueueManager`**: `get_notification_channel(origin_service: str, event_name: str, context: Optional[str] = None)`
*   **Formato**: `{prefix}:{env}:{origin_service}[:{context}]:notifications:{event_name}`
*   **Ejemplo**: `nooble4:dev:document_service:notifications:document_updated`

## 4. Conclusión

La estandarización de colas se logra mediante la **centralización de la lógica de nomenclatura en `QueueManager`**. Al utilizar `BaseWorker` y `BaseRedisClient`, los servicios se adhieren automáticamente al estándar. El rol del desarrollador es entender qué métodos de `BaseRedisClient` usar (`send_action_pseudo_sync`, `send_action_async_with_callback`, etc.) y los parámetros que estos requieren, confiando en que la comunicación subyacente está gestionada correctamente.
