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
    1.  El Cliente (ej. en AES) envía `DomainAction` (con `correlation_id` generado) a la cola `{prefijo}:{tipo_servicio_destino}:actions`.
    2.  El Cliente (ej. en AES) realiza `BLPOP` en la cola `{prefijo}:{tipo_servicio_destino}:responses:{action_name}:{correlation_id}`.
    3.  El Worker del servicio destino procesa la acción y envía la `DomainActionResponse` a la cola de respuesta específica.
*   **Ventajas**: Simple de implementar para el cliente.
*   **Consideraciones**: El cliente se bloquea. Usar timeouts en `BLPOP`.

### 4.2. Patrón Asíncrono Fire-and-Forget

*   **Flujo**:
    1.  El Cliente envía `DomainAction` a la cola `{prefijo}:{tipo_servicio_destino}:actions`.
    2.  El Cliente no espera respuesta.
*   **Uso**: Para tareas como `conversation.save_message` donde la confirmación inmediata no es crítica para el flujo principal del cliente.
*   **Consideraciones**: El servicio destino debe tener un manejo robusto de errores y reintentos, ya que el cliente no sabrá directamente si la acción falló.

### 4.3. Patrón Asíncrono con Callbacks (Reemplazando HTTP y Estandarizando)

Este patrón es crucial para tareas de larga duración donde el bloqueo no es viable (ej. ingesta y embedding de documentos), como se evidencia en `ingestion_embedding_communication.md` y flujos complejos en `inter_service_flow_communications.md`.

*   **Flujo (Ej. Ingestion -> Embedding -> Ingestion)**:
    1.  **IngestionService (Cliente de EmbeddingService)**:
        *   Genera un `correlation_id` (o `task_id` si se prefiere ese término internamente para la tarea) único para la operación de embedding completa.
        *   Define el nombre de la cola donde esperará el callback: `nooble4:dev:ingestion_service:callbacks:embedding:{correlation_id_o_task_id}`. (Ver sección de nomenclatura).
        *   Envía una `DomainAction` (ej. `embedding.generate_batch`) a la cola de acciones de EmbeddingService (ej. `nooble4:dev:embedding:actions`). 
        *   El payload (`DomainAction.data`) de esta acción **DEBE** incluir:
            *   `callback_queue_name`: El nombre de la cola donde IngestionService espera la respuesta.
            *   El `correlation_id` (o `task_id`) original para que EmbeddingService lo incluya en su respuesta de callback, permitiendo a IngestionService correlacionar el callback con la solicitud original.
            *   Los datos necesarios para la tarea de embedding (textos, etc.).
    2.  **EmbeddingService (Worker)**:
        *   Recibe y procesa la solicitud `embedding.generate_batch`.
        *   Una vez completada la generación de embeddings (o si ocurre un error), construye un nuevo `DomainAction` (que actúa como mensaje de callback).
        *   Este `DomainAction` de callback **DEBE** incluir en su payload (`DomainAction.data`):
            *   El `correlation_id` (o `task_id`) original que recibió de IngestionService.
            *   Los resultados del embedding o los detalles del error.
        *   Envía este `DomainAction` de callback a la `callback_queue_name` que fue proporcionada en la solicitud original.
    3.  **IngestionService (Worker que escucha en su cola de callbacks)**:
        *   Recibe el mensaje de callback en `nooble4:dev:ingestion_service:callbacks:embedding:{correlation_id_o_task_id}`.
        *   Utiliza el `correlation_id` (o `task_id`) del payload del callback para asociarlo con la tarea de ingesta original.
        *   Procesa el resultado (embeddings o error).
*   **Ventajas**: No bloqueante, adecuado para operaciones largas, desacoplado, permite seguimiento claro de la operación extremo a extremo mediante el `correlation_id`.
*   **Reemplazo de HTTP (Caso `IngestionService -> EmbeddingService`)**:
    *   La comunicación actual (HTTP POST para solicitud, Redis para callback) se unifica completamente a Redis.
    *   **Solicitud**: `IngestionService` (cliente) envía `DomainAction` a `nooble4:dev:embedding:actions`. El `DomainAction.data` incluye `callback_queue_name` (ej. `nooble4:dev:ingestion_service:callbacks:embedding:corr123`) y `correlation_id: "corr123"`.
    *   **Respuesta (Callback)**: `EmbeddingService` envía un `DomainAction` (tipo `embedding.batch_completed` o similar) a la `callback_queue_name` especificada. El `DomainAction.data` de este callback incluye `correlation_id: "corr123"` y los resultados.
    *   Esto elimina la necesidad del endpoint HTTP `POST /api/v1/embeddings/generate` para esta comunicación interna, haciendo el flujo más homogéneo y observable dentro del ecosistema Redis.

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
