# Gestor de Nombres de Colas (`QueueManager`)

**Módulo:** `refactorizado.common.utils.queue_manager`

## Descripción General

El `QueueManager` es una utilidad centralizada diseñada para estandarizar la generación de nombres de colas y canales de Redis utilizados para la comunicación entre los microservicios del sistema Nooble4. Asegura que todos los nombres de colas sigan una convención jerárquica y consistente, facilitando la depuración, el monitoreo y la gestión general del flujo de mensajes.

La estructura base de los nombres de cola es:
`{prefix}:{environment}:{service_segment}:{context_specific_segment?}:{type_of_queue}:{details...}`

## Inicialización

El `QueueManager` se inicializa con un prefijo global y un entorno de despliegue:

```python
from refactorizado.common.utils.queue_manager import QueueManager

# Usando valores por defecto (prefix="nooble4", environment de variable de entorno o "dev")
qm = QueueManager()

# Especificando valores
qm_prod = QueueManager(prefix="nooble4_prod", environment="production")
```

- `prefix`: Un prefijo global para todas las claves (ej. "nooble4").
- `environment`: El entorno de despliegue (ej. "dev", "staging", "production"). Si no se proporciona, intenta leer la variable de entorno `ENVIRONMENT` o usa "dev" por defecto.

## Métodos Principales

### 1. `get_action_queue(service_name: str, context: Optional[str] = None) -> str`

Genera el nombre de la cola donde un servicio específico escucha las acciones (`DomainAction`) que se le envían.

- **`service_name`**: Nombre del servicio destino que escuchará en esta cola (ej. `agent_execution_service`).
- **`context`**: (Opcional) Contexto adicional para la cola, como un `tenant_id` o `user_id`, permitiendo colas de acciones específicas.
- **Formato**: `{base}:{service_name}:{context}:actions`
- **Ejemplos**:
  - `nooble4:dev:agent_orchestrator_service:actions`
  - `nooble4:dev:embedding_service:tenant_123:actions`

### 2. `get_response_queue(origin_service: str, action_name: str, correlation_id: str, context: Optional[str] = None) -> str`

Genera un nombre de cola único para respuestas en flujos de comunicación pseudo-síncronos. El servicio que origina la solicitud (`origin_service`) escuchará en esta cola la respuesta (`DomainActionResponse`).

- **`origin_service`**: Nombre del servicio que envió la solicitud original y espera la respuesta.
- **`action_name`**: Nombre de la acción original que se invocó (ej. `agent.run`).
- **`correlation_id`**: ID único que correlaciona la solicitud con su respuesta.
- **`context`**: (Opcional) Contexto adicional relevante para el servicio de origen (ej. `session_id`).
- **Formato**: `{base}:{origin_service}:{context}:responses:{action_name}:{correlation_id}`
- **Ejemplos**:
  - `nooble4:dev:agent_orchestrator_service:responses:agent.run:abcdef12345`
  - `nooble4:dev:agent_execution_service:session_xyz:responses:document.process:uvwxyz67890`

Este nombre de cola es el que se debe usar en el campo `callback_queue_name` de un `DomainAction` cuando se utiliza el método `BaseRedisClient.send_action_pseudo_sync()`.

### 3. `get_callback_queue(origin_service: str, event_name: str, context: Optional[str] = None) -> str`

Genera el nombre de una cola para callbacks en flujos de comunicación asíncronos. El servicio que origina la solicitud (`origin_service`) escuchará en esta cola un `DomainAction` de callback.

- **`origin_service`**: Nombre del servicio que espera recibir el callback.
- **`event_name`**: Un identificador para el evento o el propósito del callback (ej. `embedding_completed`, `long_task_finished`). Este nombre ayuda a distinguir diferentes tipos de callbacks que un servicio podría esperar.
- **`context`**: (Opcional) Contexto adicional relevante para el servicio de origen (ej. `tenant_id`, `session_id`).
- **Formato**: `{base}:{origin_service}:{context}:callbacks:{event_name}`
- **Ejemplos**:
  - `nooble4:dev:agent_execution_service:tenant_123:callbacks:embedding_processing_done`
  - `nooble4:dev:orchestrator:session_abc:callbacks:agent_tool_result`

Este nombre de cola es el que se debe usar en el campo `callback_queue_name` de un `DomainAction` cuando se utiliza el método `BaseRedisClient.send_action_async_with_callback()`. El `event_name` puede estar relacionado con el `callback_action_type` esperado.

### 4. `get_notification_channel(origin_service: str, event_name: str, context: Optional[str] = None) -> str`

Genera el nombre de un canal de Redis para notificaciones usando el patrón Pub/Sub. No es utilizado directamente por los patrones de comunicación primarios de `BaseRedisClient` (`send_action_*`) pero puede ser útil para otros tipos de señalización o difusión de eventos.

- **`origin_service`**: Nombre del servicio que emite/publica la notificación.
- **`event_name`**: Nombre del evento que se está publicando.
- **`context`**: (Opcional) Contexto adicional.
- **Formato**: `{base}:{origin_service}:{context}:notifications:{event_name}`
- **Ejemplos**:
  - `nooble4:dev:ingestion_service:notifications:document_processed`
  - `nooble4:dev:user_service:user_abc:notifications:profile_updated`

## Integración con `BaseRedisClient`

El `QueueManager` es fundamental para el `BaseRedisClient` y los workers/handlers que lo utilizan:

- **Para enviar una acción a otro servicio**: Se usa `get_action_queue(service_name="nombre_servicio_destino")` para determinar la cola a la que se enviará el `DomainAction`.
- **Para comunicación pseudo-síncrona**: El cliente (emisor) usa `get_response_queue()` para generar un `callback_queue_name` único que incluye en el `DomainAction`. El servicio receptor enviará el `DomainActionResponse` a esta cola.
- **Para comunicación asíncrona con callback**: El cliente (emisor) usa `get_callback_queue()` para generar un `callback_queue_name` que incluye en el `DomainAction`. El servicio receptor enviará un nuevo `DomainAction` (el callback) a esta cola.

## Consideraciones

- La consistencia en el uso de `service_name`, `action_name`, `event_name` y `context` a través de los servicios es crucial para que el sistema de colas funcione correctamente.
- El parámetro `event_name` en `get_callback_queue` es flexible. Se recomienda que refleje claramente el propósito o el tipo de `DomainAction` esperado como callback para mejorar la legibilidad y mantenibilidad del código.
