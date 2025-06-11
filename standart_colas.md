# Propuesta de Estandarización de Colas Redis en Nooble4

## 1. Introducción

Este documento detalla una propuesta para estandarizar el uso y la nomenclatura de las colas Redis en el ecosistema Nooble4. El objetivo es asegurar una comunicación inter-servicios eficiente, predecible y fácil de monitorear, eliminando inconsistencias como el uso de HTTP para comunicaciones internas y optimizando los patrones pseudo-asíncronos y asíncronos.

Se basa en el análisis de `inter_service_communication_v2.md`, `inter_service_flow_communications.md`, y la necesidad de migrar comunicaciones como la de `IngestionService` -> `EmbeddingService` (documentada en `ingestion_embedding_communication.md`) a un modelo basado en Redis.

## 2. Principios Fundamentales para las Colas Redis

1.  **Redis como Único Bus de Mensajes Interno**: Toda comunicación interna entre microservicios de Nooble4 debe realizarse a través de colas Redis. Se debe eliminar el uso de HTTP directo para interacciones servicio-a-servicio (ej. la llamada POST de `IngestionClient` a `EmbeddingService API`).
2.  **Nomenclatura Consistente y Jerárquica**: Un esquema de nombres claro y predecible es crucial para la organización y el debugging.
3.  **Separación de Intereses**: Colas distintas para tipos de mensajes diferentes (acciones, respuestas, callbacks, notificaciones).
4.  **Soporte para Patrones de Comunicación**: La estructura de colas debe soportar eficientemente los patrones pseudo-síncrono, asíncrono fire-and-forget, y asíncrono con callbacks (si se mantiene este último).

## 3. Estandarización de Nomenclatura de Colas

Se propone la siguiente estructura de nomenclatura, que expande y formaliza las convenciones ya parcialmente en uso, inspirándose en patrones observados en `inter_service_communication_v2.md`:

`{prefijo_global}:{entorno}:{tipo_servicio_propietario_o_destino}:{nombre_instancia_o_contexto_especifico}:{tipo_cola}:{detalle_cola}`

*   **`{prefijo_global}`**: (Opcional, pero recomendado) Un prefijo global para todas las colas de Nooble4 (ej. `nooble4`). Ayuda a evitar colisiones si Redis se comparte con otras aplicaciones.
*   **`{entorno}`**: (Opcional, pero recomendado) Identificador del entorno (ej. `dev`, `staging`, `prod`). Permite aislar flujos entre entornos.
*   **`{tipo_servicio_propietario_o_destino}`**: Prefijo corto que identifica el servicio. 
    *   Para colas de `actions`, es el servicio *destino* de la acción (ej. `management`, `embedding`).
    *   Para colas de `responses` y `callbacks`, es el servicio *propietario* de la cola, es decir, el que la crea y escucha en ella (ej. el cliente que espera una respuesta o callback).
*   **`{nombre_instancia_o_contexto_especifico}`**: (Opcional) Para escenarios de multi-tenancy, instancias específicas de workers, o contextos de ejecución particulares. Ejemplos:
    *   `tenant_abc` (para colas específicas de un tenant)
    *   `session_xyz` (para colas de callback ligadas a una sesión, como en AES)
    *   `worker_instance_1` (si hay múltiples instancias especializadas)
    *   Si no se usa, esta parte se omite o se usa un valor `default`.
*   **`{tipo_cola}`**: Indica el propósito principal de la cola:
    *   `actions`: Cola principal donde los workers de un servicio *destino* escuchan nuevas `DomainActions`.
    *   `responses`: Usada para el patrón pseudo-síncrono. El nombre completo incluye el `correlation_id`. El *propietario* es el servicio cliente.
    *   `callbacks`: Colas donde un servicio *propietario* (el que inició la operación asíncrona) escucha respuestas/eventos de otros servicios.
    *   `notifications`: Para mensajes de eventos generales que no son respuestas directas a una solicitud (ej. `ingestion.document.processed`, `user.activity.logged`). El *propietario* es el servicio que emite la notificación, y los suscriptores la conocen.
    *   `dead_letter`: (Recomendado) Para mensajes que no pudieron ser procesados después de varios intentos.
*   **`{detalle_cola}`**: Información adicional específica del tipo de cola:
    *   Para `actions`: Puede ser el nombre del worker si hay varios tipos de workers en un servicio, o simplemente `default` o nada (ej. `management:default:actions` o `management:actions`).
    *   Para `responses`: `{action_name}:{correlation_id}` (ej. `execution_service:responses:get_agent_config:c1a2b3d4-e5f6-7890-1234-567890abcdef`). El servicio propietario es `execution_service`.
    *   Para `callbacks`: `{servicio_que_envia_el_callback}:{evento_o_identificador_tarea}`. Ejemplos:
        *   `ingestion_service:callbacks:embedding:batch_abc_completed` (Ingestion Service espera un callback de Embedding Service para el batch 'abc').
        *   `execution_service:tenant_xyz:session_123:callbacks:query:rag_results` (Execution Service, para un tenant y sesión específicos, espera un callback de Query Service).
    *   Para `notifications`: `{nombre_evento_o_topico}` (ej. `ingestion:notifications:document_processed`, `user_service:notifications:user_created`).

**Ejemplos Completos (suponiendo `nooble4:dev` como prefijo global y de entorno):**

*   **Cola de Acciones para AgentManagementService**:
    `nooble4:dev:management:actions` (o `nooble4:dev:management:default:actions`)
*   **Cola de Acciones para EmbeddingService (específica para un tenant si fuera necesario)**:
    `nooble4:dev:embedding:tenant_xyz:actions`
*   **Cola de Respuesta para una solicitud `get_agent_config` (cliente es ExecutionService, destino es ManagementService)**:
    El cliente (ExecutionService) crea y escucha en: `nooble4:dev:execution_service:responses:get_agent_config:c1a2b3d4-e5f6-7890-1234-567890abcdef`
    ManagementService envía la respuesta a esta cola.
*   **Cola de Callbacks donde AgentExecutionService (AES) espera resultados de QueryService para una sesión específica**:
    AES crea y escucha en: `nooble4:dev:execution_service:tenant_abc:session_123:callbacks:query:rag_results`
    QueryService envía el callback a esta cola.
*   **Cola de Callbacks donde IngestionService espera resultados de EmbeddingService para un `task_id` específico (reemplazando HTTP)**:
    IngestionService crea y escucha en: `nooble4:dev:ingestion_service:callbacks:embedding:task_987efg`
    EmbeddingService envía el callback a esta cola. El `task_id` (o `correlation_id`) debe viajar en el payload del mensaje de callback para la correlación final por parte de IngestionService.
*   **Cola de Notificaciones de IngestionService sobre documentos procesados**:
    `nooble4:dev:ingestion_service:notifications:document_processed`

## 4. Patrones de Comunicación y Colas Asociadas

### 4.1. Patrón Pseudo-Síncrono

*   **Flujo**:
    1.  El **Cliente** (ej. `ServiceA` llamando a `ServiceB`):
        *   Genera un `action_id` (nuevo UUID), `correlation_id` (nuevo UUID para este request-response), y `trace_id` (propagar si existe, o nuevo UUID).
        *   Define su propia cola de respuesta única: `client_response_queue = "nooble4:dev:serviceA:responses:{action_type_short}:{correlation_id}"`.
        *   Construye `DomainAction` con:
            *   `action_id`, `action_type` (ej. `serviceB.entity.verb`)
            *   `correlation_id`, `trace_id`
            *   `origin_service` (nombre de `ServiceA`)
            *   `callback_queue_name = client_response_queue` (para que `ServiceB` sepa dónde responder)
            *   `data` (payload de la solicitud)
        *   Envía esta `DomainAction` a la cola de acciones de `ServiceB` (ej. `nooble4:dev:serviceB:actions`).
    2.  El **Cliente** (`ServiceA`) inmediatamente realiza `BLPOP` en su `client_response_queue` (con un timeout).
    3.  El **Worker de `ServiceB`**:
        *   Recibe la `DomainAction`.
        *   Procesa la acción.
        *   Construye `DomainActionResponse` con:
            *   `success` (True/False)
            *   `correlation_id` (copiado del `DomainAction` original)
            *   `trace_id` (copiado del `DomainAction` original)
            *   `action_type_response_to` (el `action_type` del `DomainAction` original)
            *   `data` (payload de la respuesta) o `error` (modelo `ErrorDetail`).
        *   Envía esta `DomainActionResponse` a la cola especificada en `original_action.callback_queue_name`.
    4.  El **Cliente** (`ServiceA`) recibe la `DomainActionResponse` de su `BLPOP`.
*   **Ventajas**: Comportamiento similar a una llamada de función síncrona para el cliente.
*   **Consideraciones**: El cliente se bloquea. Es crucial usar timeouts en `BLPOP`.

### 4.2. Patrón Asíncrono Fire-and-Forget

*   **Flujo**:
    1.  El Cliente envía `DomainAction` a la cola `{prefijo}:{tipo_servicio_destino}:actions`.
    2.  El Cliente no espera respuesta.
*   **Uso**: Para tareas como `conversation.save_message` donde la confirmación inmediata no es crítica para el flujo principal del cliente.
*   **Consideraciones**: El servicio destino debe tener un manejo robusto de errores y reintentos, ya que el cliente no sabrá directamente si la acción falló.

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
