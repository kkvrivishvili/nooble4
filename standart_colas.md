# Estándar de Colas Redis en Nooble4

> **Última Revisión:** 14 de Junio de 2024
> **Estado:** Aprobado y en implementación.
> **Clase de Referencia:** `common.utils.queue_manager.QueueManager`

## 1. Introducción

Este documento establece el estándar para la nomenclatura de colas Redis en Nooble4. El objetivo es simple: **nadie debe construir nombres de colas manualmente**. Toda la lógica de nomenclatura está centralizada en la clase `QueueManager`.

## 2. El `QueueManager`: La Única Fuente de Verdad

La clase `QueueManager`, ubicada en `common/utils/queue_manager.py`, es la responsable de generar todos los nombres de colas de manera consistente y predecible. Se inicializa con los settings de la aplicación (`CommonAppSettings`) para acceder a valores como el prefijo global (`nooble4`) y el entorno (`dev`, `prod`).

### 2.1. Uso en `BaseWorker` y `BaseRedisClient`

Tanto `BaseWorker` (para escuchar) como `BaseRedisClient` (para enviar) utilizan una instancia de `QueueManager` internamente. Esto garantiza que el servicio que envía un mensaje y el que lo recibe usen exactamente la misma convención para nombrar la cola.

## 3. Formato de las Colas Generadas

Aunque no necesitas construir estos nombres, es útil conocer el patrón para fines de depuración y monitoreo en Redis.

### a) Colas de Acciones

Son las colas donde los workers escuchan por trabajo nuevo. `BaseWorker` la usa para saber de dónde leer mensajes.

*   **Método**: `QueueManager.get_action_queue_name(service_name: str)`
*   **Formato**: `{prefix}:{env}:{service_name}:actions`
*   **Ejemplo**: `nooble4:dev:embedding:actions`

### b) Colas de Respuesta (Pseudo-Síncronas)

Son colas temporales creadas por `BaseRedisClient` para cada llamada pseudo-síncrona.

*   **Método**: `QueueManager.get_response_queue_name(correlation_id: str)`
*   **Formato**: `{prefix}:{env}:responses:{correlation_id}`
*   **Ejemplo**: `nooble4:dev:responses:a1b2c3d4-e5f6-7890-1234-567890abcdef`

`BaseRedisClient` asigna este nombre al campo `callback_queue_name` de la `DomainAction` antes de enviarla. El worker receptor simplemente usa ese campo para saber dónde enviar la `DomainActionResponse`.

### c) Colas de Callback (Asíncronas)

Para los flujos asíncronos con callback, el servicio que inicia la acción es responsable de definir el nombre de la cola donde espera la respuesta y pasarlo en el campo `callback_queue_name` de la `DomainAction`. El `QueueManager` puede usarse para construir un nombre consistente si se desea.

## 4. Conclusión

La estandarización de colas se logra mediante la **centralización**, no mediante la documentación de un formato manual. Al usar `BaseWorker` y `BaseRedisClient`, te adhieres automáticamente al estándar de colas sin necesidad de conocer los detalles de implementación del `QueueManager`.

### 4.3. Patrón Asíncrono con Callbacks (Reemplazando HTTP y Estandarizando)

Este patrón es crucial para tareas de larga duración donde el bloqueo no es viable (ej. ingesta y embedding de documentos).

*   **Flujo (Ej. `ServiceA` solicita una tarea a `ServiceB` y espera un callback)**:
    1.  **`ServiceA` (Cliente de `ServiceB`)**:
        *   Genera `action_id` (nuevo UUID para la solicitud), `correlation_id` (nuevo UUID para correlacionar esta solicitud con su futuro callback), y `trace_id` (propagar o nuevo).
        *   Define la cola donde esperará el callback: `client_callback_queue = "nooble4:dev:serviceA:callbacks:serviceB_task_result:{correlation_id}"`.
        *   Define el tipo de acción que espera en el callback: `expected_callback_action_type = "serviceB.task.completed"`.
        *   Construye la `DomainAction` de solicitud con:
            *   `action_id`, `action_type` (ej. `serviceB.task.start`)
            *   `correlation_id` (el generado arriba)
            *   `trace_id`
            *   `origin_service` (nombre de `ServiceA`)
            *   `callback_queue_name = client_callback_queue`
            *   `callback_action_type = expected_callback_action_type`
            *   `data` (payload para la tarea de `ServiceB`)
        *   Envía esta `DomainAction` a la cola de acciones de `ServiceB` (ej. `nooble4:dev:serviceB:actions`).
        *   `ServiceA` guarda el `correlation_id` para poder identificar el callback cuando llegue.
    2.  **`ServiceB` (Worker)**:
        *   Recibe y procesa la solicitud `serviceB.task.start`.
        *   Realiza la tarea de larga duración.
    3.  **`ServiceB` (Handler, una vez completada la tarea)**:
        *   Construye un *nuevo* `DomainAction` (el mensaje de callback) con:
            *   `action_id` (nuevo UUID para este mensaje de callback)
            *   `action_type` (el `callback_action_type` recibido en la solicitud original, ej. `serviceB.task.completed`)
            *   `correlation_id` (el `correlation_id` de la solicitud original, **crucial para la correlación por `ServiceA`**)
            *   `trace_id` (propagado de la solicitud original)
            *   `origin_service` (nombre de `ServiceB`, ya que es el origen de *este* mensaje de callback)
            *   `data` (los resultados de la tarea o detalles del error, como un modelo Pydantic serializado).
            *   `callback_queue_name` y `callback_action_type` son `None` en este mensaje de callback, a menos que este callback a su vez espere otro callback (encadenamiento).
        *   Envía este `DomainAction` de callback a la `callback_queue_name` que fue proporcionada en la solicitud original (ej. `nooble4:dev:serviceA:callbacks:serviceB_task_result:{original_correlation_id}`).
    4.  **`ServiceA` (Worker que escucha en su `client_callback_queue`)**:
        *   Recibe el `DomainAction` de callback.
        *   Extrae el `correlation_id` del mensaje de callback.
        *   Usa este `correlation_id` para asociar el callback con la solicitud original que `ServiceA` envió.
        *   Procesa los resultados o el error del `data` del callback.
*   **Ventajas**: No bloqueante, adecuado para operaciones largas, desacoplado, permite seguimiento claro.
*   **Reemplazo de HTTP (Caso `IngestionService -> EmbeddingService`)**:
    *   La comunicación actual (HTTP POST para solicitud, Redis para callback) se unifica completamente a Redis.
    *   **Solicitud (`IngestionService` a `EmbeddingService`)**: `IngestionService` envía `DomainAction` a `nooble4:dev:embedding:actions`.
        *   `action_type`: `embedding.generate_batch`
        *   `correlation_id`: `corr123` (generado por Ingestion)
        *   `trace_id`: `trace789`
        *   `origin_service`: `IngestionService`
        *   `callback_queue_name`: `nooble4:dev:ingestion_service:callbacks:embedding_result:corr123`
        *   `callback_action_type`: `embedding.batch.generated` (o `embedding.batch.completed`)
        *   `data`: `{ "texts": [...], ... }`
    *   **Respuesta (Callback de `EmbeddingService` a `IngestionService`)**: `EmbeddingService` envía un *nuevo* `DomainAction` a la `callback_queue_name` (`nooble4:dev:ingestion_service:callbacks:embedding_result:corr123`).
        *   `action_type`: `embedding.batch.generated` (el `callback_action_type` de la solicitud)
        *   `correlation_id`: `corr123` (el `correlation_id` de la solicitud original)
        *   `trace_id`: `trace789` (propagado)
        *   `origin_service`: `EmbeddingService`
        *   `data`: `{ "results": [...], "status": "success" }` o `{ "error": {...}, "status": "failure" }`
    *   Esto elimina la necesidad del endpoint HTTP `POST /api/v1/embeddings/generate` para esta comunicación interna.

### 4.4. Patrón de Orquestación Avanzada: Ciclo de Agente Iterativo

Un caso de uso avanzado y crítico en Nooble4 es el del `AgentExecutionService` (AES) orquestando un ciclo de "razonamiento y uso de herramientas" (similar a ReAct) para responder a una única solicitud de usuario. Este escenario demuestra cómo los diferentes identificadores trabajan en conjunto para mantener la trazabilidad en flujos complejos.

*   **Escenario**: Un usuario le pide al agente: "Resume el último documento sobre 'Proyecto X' y compáralo con las notas de la reunión de ayer".

*   **Identificadores de Alto Nivel (Constantes durante todo el ciclo)**:
    *   `task_id`: Representa la solicitud completa del usuario. Permanece igual en todos los pasos.
    *   `trace_id`: Se genera al inicio y se propaga a todas las acciones para la observabilidad de la traza completa.
    *   `session_id`, `tenant_id`: Mantienen el contexto de la conversación y del tenant.

*   **Flujo Iterativo con Múltiples `correlation_id`**:
    1.  **AES -> QueryService (Paso 1: Búsqueda de 'Proyecto X')**: AES necesita encontrar el documento. Inicia una llamada pseudo-síncrona.
        *   `action_type`: `query.rag.execute`
        *   `task_id`: `task_123`
        *   `correlation_id`: `corr_A` (para esta búsqueda específica)
        *   `action_id`: `uuid_1`
    2.  **QueryService -> AES (Respuesta)**: Devuelve el documento encontrado.
        *   `correlation_id`: `corr_A`
    3.  **AES -> QueryService (Paso 2: Búsqueda de 'notas de la reunión')**: AES ahora busca el segundo documento. Inicia otra llamada pseudo-síncrona.
        *   `action_type`: `query.rag.execute`
        *   `task_id`: `task_123`
        *   `correlation_id`: `corr_B` (un nuevo ID para esta segunda búsqueda)
        *   `action_id`: `uuid_2`
    4.  **QueryService -> AES (Respuesta)**: Devuelve las notas.
        *   `correlation_id`: `corr_B`
    5.  **AES -> Groq (Paso 3: Generación del resumen y comparación)**: AES tiene toda la información. Llama al LLM a través de un servicio (ej. `LLMService`) para generar la respuesta final.
        *   `action_type`: `llm.generate.text`
        *   `task_id`: `task_123`
        *   `correlation_id`: `corr_C` (un nuevo ID para la llamada al LLM)
        *   `action_id`: `uuid_3`
    6.  **Groq -> AES (Respuesta)**: Devuelve el texto final.
        *   `correlation_id`: `corr_C`

*   **Conclusión del Patrón**:
    *   Un único `task_id` agrupa toda la operación de alto nivel.
    *   Múltiples `correlation_id` se utilizan para gestionar cada "diálogo" o transacción pseudo-síncrona individual que el orquestador (AES) realiza con otros servicios.
    *   Cada mensaje individual (solicitud o respuesta) tiene su propio `action_id` único para logging y depuración a nivel de mensaje.

Este modelo permite al orquestador mantener el estado de la tarea principal (`task_id`) mientras gestiona de forma atómica y rastreable cada una de las sub-tareas necesarias para completarla.

## 5. Gestión de Colas y Workers

*   **`DomainQueueManager`**: Esta clase (o una similar) debería ser la responsable de construir los nombres de las colas de manera consistente, basándose en la configuración del servicio y los parámetros de la acción.
*   **Workers**: Los `BaseWorker` deben ser configurados para escuchar en las colas de `actions` apropiadas. Workers especializados (o el mismo worker con lógica de despacho) pueden escuchar en colas de `callbacks` o `notifications` si es necesario.
*   **Dead Letter Queues (DLQ)**:
    *   Implementar un mecanismo de DLQ para cada cola de `actions` principal.
    *   Si un mensaje falla repetidamente en ser procesado, se mueve a la DLQ (ej. `nooble4:dev:management:actions:dead_letter`) para análisis manual o re-procesamiento.
    *   Esto evita que mensajes problemáticos bloqueen el procesamiento de otros mensajes y previene la pérdida de datos.

## 6. Transición y Eliminación de HTTP Interno

*   **Prioridad**: Identificar todas las comunicaciones internas servicio-a-servicio que actualmente usan HTTP.
*   **Plan de Migración (ej. Ingestion -> Embedding)**:
    1.  Asegurar que `EmbeddingService` pueda manejar `DomainActions` para `embedding.generate` (o similar) recibidas vía Redis.
    2.  Modificar `EmbeddingService` para que envíe su respuesta/callback a la `callback_queue` especificada en la `DomainAction` de solicitud.
    3.  Modificar `IngestionService` (su `EmbeddingClient`) para enviar la solicitud como `DomainAction` vía Redis en lugar de HTTP POST.
    4.  Asegurar que `IngestionWorker` escuche en la cola de callbacks correcta para recibir la respuesta de `EmbeddingService`.
    5.  Una vez verificado, el endpoint HTTP interno en `EmbeddingService` puede ser deshabilitado o eliminado.

## 7. Beneficios de la Estandarización

*   **Simplicidad y Consistencia**: Un único mecanismo de transporte (Redis) para toda la comunicación interna.
*   **Observabilidad Mejorada**: Más fácil monitorear y rastrear mensajes a través de un sistema de colas uniforme.
*   **Robustez**: Patrones claros para manejo de errores, reintentos (a nivel de worker) y DLQs.
*   **Mantenibilidad**: Código más predecible y fácil de entender en todos los servicios.

Al implementar estas directrices, Nooble4 puede lograr un sistema de comunicación por colas más eficiente, resiliente y estandarizado.
