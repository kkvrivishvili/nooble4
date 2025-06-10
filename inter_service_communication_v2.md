# Documento0 de Comunicación Inter-Servicios en Nooble4 (Versión 2)

## 1. Introducción Global (Versión 2)

### 1.1. Objetivo Revisado

Esta versión 2 del documento de comunicación inter-servicios tiene como objetivo proporcionar un análisis exhaustivo, ordenado y detallado de todos los patrones de comunicación basados en colas Redis dentro del ecosistema Nooble4. Busca no solo documentar el estado actual, sino también servir como una base para la identificación proactiva de inconsistencias, áreas de mejora, y posibles puntos de fallo. El fin último es mejorar la robustez, mantenibilidad y comprensión del sistema de comunicación distribuida.

Se enfoca en:

*   Las colas Redis utilizadas.
*   Los payloads exactos intercambiados (solicitud, respuesta, callback).
*   Las responsabilidades de cada servicio como emisor y receptor.
*   Los patrones de comunicación explícitos (pseudo-síncrono, asíncrono, etc.).
*   El estado de implementación y las observaciones críticas para cada flujo.

### 1.2. Paradigmas de Comunicación en Nooble4

El sistema Nooble4 emplea principalmente los siguientes paradigmas para la comunicación inter-servicios:

*   **Colas Redis como Bus de Mensajes**: Redis actúa como el intermediario principal para el intercambio de mensajes entre servicios.
*   **`DomainActions`**: Un patrón de objeto de mensaje estandarizado (`DomainAction`) se utiliza para encapsular solicitudes y datos. Estos objetos son serializados y publicados en colas Redis específicas.
*   **Patrón Pseudo-Síncrono**: Para operaciones donde un servicio cliente necesita una respuesta antes de continuar, se implementa un patrón pseudo-síncrono. El cliente envía una `DomainAction` con un `correlation_id` único y luego realiza una operación de bloqueo (como `BLPOP`) en una cola de respuesta específica (generalmente nombrada `<servicio_destino>:responses:<accion>:<correlation_id>`) hasta que llega la respuesta.
*   **Patrón Asíncrono Fire-and-Forget**: Para operaciones que no requieren una respuesta inmediata o confirmación, el servicio cliente publica una `DomainAction` en una cola y no espera una respuesta directa. El servicio receptor procesa la acción de forma asíncrona.
*   **Patrón Asíncrono con Callbacks**: En algunos casos, un servicio puede iniciar una operación en otro y, en lugar de esperar síncronamente, el servicio receptor enviará una `DomainAction` de "callback" a una cola específica del servicio original una vez que la tarea se complete (o falle). Esto se usa para notificar resultados de tareas de larga duración.

### 1.3. Convenciones y Terminología

*   **AES**: Agent Execution Service
*   **AMS**: Agent Management Service
*   **CS**: Conversation Service
*   **ES**: Embedding Service
*   **IS**: Ingestion Service
*   **QS**: Query Service
*   **AOS**: Agent Orchestrator Service
*   **`{correlation_id}`**: Un identificador único (generalmente UUID) usado para emparejar solicitudes con respuestas en patrones pseudo-síncronos.
*   **`{tenant_id}`**: Identificador del inquilino/cliente.
*   **`{session_id}`**: Identificador de una sesión de conversación específica.
*   **Payload**: Se refiere al contenido de datos dentro de una `DomainAction` o una respuesta.

---

## 2. Análisis Detallado por Servicio

### 2.1. Agent Execution Service (AES)

El Agent Execution Service (AES) es el núcleo de la ejecución de agentes conversacionales. Orquesta las interacciones con otros servicios para obtener configuraciones, contexto, generar embeddings, realizar búsquedas RAG y persistir mensajes.

#### A. Comunicaciones Salientes (AES como Cliente)

##### Interacción 2.1.1: `AES -> Agent Management Service (AMS): Obtener Configuración de Agente`

*   **Contexto y Justificación Detallada**: Para que AES pueda ejecutar un agente específico, primero debe obtener su configuración completa. Esta configuración incluye el system prompt, el modelo LLM a utilizar, la temperatura, las herramientas habilitadas, las colecciones de conocimiento para RAG (con sus respectivos modelos de embedding), y cualquier otro parámetro relevante. AMS es la fuente autoritativa de esta información.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.agent_management_client.AgentManagementClient.get_agent_config()`.
*   **Destino (Servidor)**: `Agent Management Service`, procesado por `agent_management_service.workers.management_worker.ManagementWorker` (que a su vez utiliza handlers como `AgentManagementHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `management.get_agent_config`
    *   Cola de Solicitud: `management.actions` (el `DomainQueueManager` puede añadir prefijos o sufijos basados en `tenant_id` si la configuración del worker en AMS está particionada por tenant, ej. `management:{tenant_id}:actions`).
    *   Patrón de Cola de Respuesta: `management:responses:get_agent_config:{correlation_id}`
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud**:
        ```json
        {
          "action_id": "<uuid4>", // Autogenerado por DomainAction
          "action_type": "management.get_agent_config",
          "task_id": null, // No establecido explícitamente por el cliente AES para esta acción
          "tenant_id": null, // No establecido a nivel raíz por el cliente AES; presente en 'data'
          "tenant_tier": null, // No establecido explícitamente por el cliente AES
          "timestamp": "<iso_timestamp>", // Autogenerado por DomainAction
          "session_id": null, // No relevante para esta acción
          "correlation_id": null, // No establecido a nivel raíz por el cliente AES; presente en 'data'
          "data": {
            "agent_id": "<uuid_del_agente>",
            "tenant_id": "<id_del_tenant>",
            "correlation_id": "<uuid_para_correlacion_respuesta>" // Generado por AgentManagementClient
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `data.agent_id`: El UUID del agente cuya configuración se solicita.
          *   `data.tenant_id`: El UUID del tenant al que pertenece el agente. Esencial para que AMS localice el agente correcto y aplique cualquier lógica específica del tenant.
          *   `data.correlation_id`: Utilizado por AES para escuchar en la cola de respuesta correcta.

    *   **Payload de Respuesta (Esperado por AES)**:
        ```json
        {
          "success": true, // boolean: indica si la operación fue exitosa
          "correlation_id": "<mismo_uuid_de_la_solicitud>", // Confirma la correlación
          "agent_config": { // Objeto que contiene la configuración detallada del agente
            "agent_id": "<uuid_del_agente>",
            "name": "Nombre del Agente",
            "system_prompt": "Este es el prompt del sistema para el agente...",
            "model_name": "proveedor/modelo-llm", // ej. "openai/gpt-4-turbo"
            "temperature": 0.7,
            "max_tokens": 1024,
            "tools": [
              { "tool_name": "nombre_herramienta_1", "config": { /* ... */ } },
              { "tool_name": "nombre_herramienta_2", "config": { /* ... */ } }
            ],
            "collections": [
              { 
                "collection_id": "<uuid_collection_1>", 
                "name": "Nombre Colección 1",
                "embedding_model": "proveedor/modelo-embedding-collection-1" // ej. "openai/text-embedding-ada-002"
              },
              { 
                "collection_id": "<uuid_collection_2>", 
                "name": "Nombre Colección 2",
                "embedding_model": "proveedor/modelo-embedding-collection-2"
              }
            ],
            "metadata": { /* Otros metadatos relevantes del agente */ },
            "tier_config": { /* Configuraciones específicas del tier del tenant */ }
          },
          "error": null // string: mensaje de error si success es false
        }
        ```
        *Explicación de Campos Clave (Respuesta)*:
          *   `success`: Fundamental para que AES sepa si puede proceder.
          *   `agent_config`: Debe ser exhaustivo. Incluye no solo la configuración básica del LLM, sino también las herramientas asociadas y, crucialmente, la lista de `collections` con sus `collection_id` y los `embedding_model` específicos para cada una. Esto es vital para que AES pueda luego interactuar correctamente con `QueryService` y `EmbeddingService` para RAG.
*   **Estado de Implementación**: Completamente Implementado.

##### Interacción 2.1.2: `AES -> Conversation Service (CS): Obtener Historial de Conversación`

*   **Contexto y Justificación Detallada**: Para que un agente pueda responder de manera coherente y contextualizada, AES necesita obtener el historial de la conversación actual. Esta información se solicita al Conversation Service (CS), que es el responsable de persistir y gestionar los intercambios de mensajes.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.conversation_client.ConversationServiceClient.get_conversation_history()`.
*   **Destino (Servidor)**: `Conversation Service`, procesado por `conversation_service.workers.conversation_worker.ConversationWorker` (que a su vez utiliza `conversation_service.handlers.conversation_handler.ConversationHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `conversation.get_history`
    *   Cola de Solicitud: `conversation.actions` (El `DomainQueueManager` puede añadir prefijos/sufijos basados en `tenant_id`, ej. `conversation:{tenant_id}:actions`).
    *   Patrón de Cola de Respuesta: `conversation:responses:get_history:{correlation_id}`
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud** (según el documento original y la implementación del cliente):
        ```json
        {
          "action_id": "<uuid4>", // Autogenerado por DomainAction
          "action_type": "conversation.get_history",
          "task_id": null, // No establecido explícitamente por el cliente AES
          "tenant_id": "<id_del_tenant>", // Establecido a nivel raíz
          "tenant_tier": null, // No establecido explícitamente por el cliente AES
          "timestamp": "<iso_timestamp>", // Autogenerado por DomainAction
          "session_id": "<id_de_sesion>", // Establecido a nivel raíz
          "correlation_id": "<uuid_para_correlacion_respuesta>", // Establecido a nivel raíz y también en 'data'
          "data": {
            "limit": 100, // Ejemplo de límite, el cliente puede configurarlo
            "include_system": true, // Ejemplo, el cliente puede configurarlo
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado aquí
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `tenant_id`: Identificador del tenant, crucial para el enrutamiento y la segregación de datos en CS.
          *   `session_id`: Identificador de la conversación específica cuyo historial se solicita.
          *   `correlation_id` (raíz y en `data`): Usado por AES para escuchar en la cola de respuesta correcta. La presencia en `data` parece redundante si ya está a nivel raíz.
          *   `data.limit`: Número máximo de mensajes a devolver.
          *   `data.include_system`: Booleano para incluir o no mensajes de sistema en el historial.

    *   **Payload de Respuesta (Esperado por AES)**:
        ```json
        {
          "success": true, // boolean: indica si la operación fue exitosa
          "correlation_id": "<mismo_uuid_de_la_solicitud>", // Confirma la correlación
          "data": {
            "messages": [
              { 
                "role": "user", 
                "content": "Hola agente", 
                "timestamp": "<iso_timestamp_mensaje_1>",
                "message_id": "<uuid_mensaje_1>",
                "metadata": { /* metadatos adicionales del mensaje */ }
              },
              { 
                "role": "assistant", 
                "content": "Hola, ¿cómo puedo ayudarte hoy?", 
                "timestamp": "<iso_timestamp_mensaje_2>",
                "message_id": "<uuid_mensaje_2>",
                "metadata": { /* metadatos adicionales del mensaje */ }
              }
              // ... más mensajes
            ]
          },
          "error": null // string: mensaje de error si success es false
        }
        ```
        *Explicación de Campos Clave (Respuesta)*:
          *   `success`: Indica si la obtención del historial fue exitosa.
          *   `data.messages`: Lista de objetos de mensaje. Cada mensaje debe contener al menos `role`, `content`, y idealmente `timestamp`, `message_id` y `metadata` para un contexto completo.
*   **Estado de Implementación**: Implementado tanto en el cliente AES como (presumiblemente) en el Conversation Service worker/handler.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Redundancia de `correlation_id`**: El `correlation_id` se envía tanto a nivel raíz del `DomainAction` como dentro del objeto `data`. Sería más limpio tenerlo solo a nivel raíz, ya que su propósito es para el emparejamiento de la `DomainAction` en sí, no como un dato de negocio intrínseco de la solicitud de historial.
    *   **Completitud del Payload de Mensaje**: El documento original sugiere que el payload de respuesta debería incluir metadatos adicionales por mensaje (`message_id`, `timestamp`, `metadata`). Esto es crucial para la trazabilidad y para que el agente pueda tener un contexto lo más rico posible. El ejemplo de respuesta se ha actualizado para reflejar esto.
    *   **Manejo de Errores**: AES debe manejar adecuadamente los casos donde `success` es `false` en la respuesta (ej. sesión no encontrada, error en CS).
    *   **Consistencia de la Cola de Respuesta**: El cliente AES espera la respuesta en `conversation:responses:get_history:{correlation_id}`. Es vital que el `ConversationWorker` en CS envíe la respuesta exactamente a esta cola. (Nota: El análisis previo del documento original identificó una posible discrepancia aquí para `get_history` donde el worker podría estar usando `conversation:responses:{correlation_id}`. Esto necesita ser verificado y corregido si es el caso, ya que es **CRÍTICO** para la comunicación).
    *   **Paginación/Límites**: El campo `limit` permite controlar la cantidad de historial. Considerar si se necesita un mecanismo de paginación más robusto para conversaciones muy largas.

##### Interacción 2.1.3: `AES -> Conversation Service (CS): Guardar Mensaje en Conversación`

*   **Contexto y Justificación Detallada**: Después de que un agente genera una respuesta, o cuando el usuario envía un nuevo mensaje, AES necesita persistir este mensaje en el historial de la conversación. Esta tarea se delega al Conversation Service.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.conversation_client.ConversationServiceClient.save_message()`.
*   **Destino (Servidor)**: `Conversation Service`, procesado por `conversation_service.workers.conversation_worker.ConversationWorker` (utilizando `conversation_service.handlers.conversation_handler.ConversationHandler`).
*   **Patrón de Comunicación**: Asíncrono Fire-and-Forget (según el análisis del documento original, no se espera una respuesta directa para esta acción, aunque el cliente *podría* estar implementado para esperar una si la cola de respuesta se especificara).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `conversation.save_message`
    *   Cola de Solicitud: `conversation.actions` (El `DomainQueueManager` puede añadir prefijos/sufijos basados en `tenant_id`).
    *   Cola de Respuesta: No se utiliza explícitamente para esperar una respuesta en un patrón síncrono. Si CS enviara una confirmación, necesitaría una cola designada, pero el cliente AES no parece esperar una.
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud** (basado en el cliente AES y la lógica común):
        ```json
        {
          "action_id": "<uuid4>",
          "action_type": "conversation.save_message",
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion>",
          "correlation_id": "<uuid_opcional_para_tracking_interno_en_aes>", // Puede o no ser usado por AES para tracking, no para respuesta.
          "timestamp": "<iso_timestamp>",
          "data": {
            "message": {
              "role": "user", // o "assistant", "system"
              "content": "Este es el contenido del mensaje.",
              "message_id": "<uuid_del_mensaje_cliente_o_generado>", // Opcional, CS podría generar el suyo si no se provee.
              "timestamp": "<iso_timestamp_del_mensaje>", // Puede ser el mismo que el de la acción o específico del mensaje.
              "metadata": { 
                /* metadatos adicionales del mensaje, ej. tool_calls, tool_outputs */
                "user_id": "<id_del_usuario_si_aplica>",
                "agent_id": "<id_del_agente_si_es_respuesta_de_agente>"
              }
            }
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `data.message`: Objeto que contiene toda la información del mensaje a guardar.
          *   `data.message.role`: Indica el origen del mensaje (usuario, asistente, sistema).
          *   `data.message.content`: El texto del mensaje.
          *   `data.message.message_id`: Un identificador único para el mensaje. Si AES lo genera, CS debería usarlo. Si no, CS debería generarlo.
          *   `data.message.timestamp`: Fecha y hora del mensaje.
          *   `data.message.metadata`: Metadatos adicionales, como información del usuario, agente, o datos de herramientas si es un mensaje de asistente con ejecución de herramientas.

    *   **Payload de Respuesta (Si existiera y se esperase)**:
        El cliente AES `save_message` no espera una respuesta síncrona. Si CS enviara una confirmación (por ejemplo, a una cola de eventos o a una cola de respuesta si se especificara un `correlation_id` con ese propósito), podría ser algo como:
        ```json
        {
          "success": true,
          "correlation_id": "<uuid_de_la_solicitud_si_se_uso_para_esto>",
          "data": {
            "message_id": "<uuid_del_mensaje_guardado_en_cs>",
            "session_id": "<id_de_sesion>"
          },
          "error": null
        }
        ```
*   **Estado de Implementación**: Implementado en el cliente AES. Se asume implementado en CS.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Confirmación de Escritura**: El patrón actual es fire-and-forget. Esto significa que AES no tiene confirmación directa de que el mensaje se guardó exitosamente. Para casos críticos, podría ser deseable un mecanismo de confirmación, aunque sea asíncrono (ej. un evento `message.saved` emitido por CS).
    *   **Idempotencia y `message_id`**: Si AES provee un `message_id`, CS debería usarlo y manejar posibles escrituras duplicadas de forma idempotente (ej. si AES reintenta enviar el mismo mensaje). Si AES no provee `message_id`, CS debe generarlo y, idealmente, podría devolverlo (aunque no en el patrón actual).
    *   **Consistencia del Historial**: Es crucial que los mensajes se guarden en el orden correcto y con timestamps precisos para mantener la integridad del historial de conversación.
    *   **Error Handling**: Sin una respuesta directa, AES no puede saber inmediatamente si hubo un error al guardar el mensaje en CS (ej. validación fallida, error de base de datos en CS). Esto podría llevar a inconsistencias si AES asume que el mensaje se guardó. La monitorización y logs en CS son vitales.
    *   **Payload de `metadata`**: El contenido de `data.message.metadata` debe ser bien definido y estandarizado para permitir un filtrado y análisis útil posteriormente. Por ejemplo, incluir `agent_id` si es un mensaje de un agente, o `tool_id` si está relacionado con la ejecución de una herramienta.

##### Interacción 2.1.4: `AES -> Embedding Service (ES): Generar Embeddings (Síncrono)`

*   **Contexto y Justificación Detallada**: Para realizar búsquedas semánticas (RAG) o para ciertas funcionalidades de agentes que requieren representaciones vectoriales de texto, AES necesita convertir texto en embeddings. Esta tarea se delega al Embedding Service.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.embedding_client.EmbeddingClient.generate_embeddings_sync()`.
*   **Destino (Servidor)**: `Embedding Service`, procesado por `embedding_service.workers.embedding_worker.EmbeddingWorker` (utilizando `embedding_service.handlers.embedding_handler.EmbeddingHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `embedding.generate.sync`
    *   Cola de Solicitud: `embedding.actions` (El `DomainQueueManager` puede añadir prefijos/sufijos basados en `tenant_id`).
    *   Patrón de Cola de Respuesta: `embedding:responses:generate:{correlation_id}`
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud** (basado en el cliente AES y la lógica común):
        ```json
        {
          "action_id": "<uuid4>",
          "action_type": "embedding.generate.sync",
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_contextual>", // Para logging/tracking
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "texts": [
              "Texto 1 para generar embedding",
              "Texto 2 para generar embedding"
            ],
            "model": "<nombre_del_modelo_de_embedding_opcional>", // ej. "openai/text-embedding-ada-002"
            "collection_id": "<uuid_de_la_coleccion_asociada_opcional>", // Para contexto o si el modelo es específico de la colección
            "metadata": { /* metadatos adicionales para logging o contexto */ },
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado aquí
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `data.texts`: Lista de strings para los cuales se generarán embeddings.
          *   `data.model`: (Opcional) Especifica el modelo de embedding a utilizar. Si no se provee, ES usará un modelo por defecto para el tenant o la colección.
          *   `data.collection_id`: (Opcional) Puede usarse para indicar que los embeddings están relacionados con una colección específica, lo que podría influir en la elección del modelo o en la lógica de negocio en ES.
          *   `correlation_id` (raíz y en `data`): Usado por AES para esperar la respuesta. Redundante en `data`.

    *   **Payload de Respuesta (Esperado por AES)**:
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "embeddings": [
              [0.001, 0.002, ..., -0.005], // Embedding para "Texto 1"
              [-0.003, 0.004, ..., 0.001]  // Embedding para "Texto 2"
            ],
            "model_used": "<nombre_del_modelo_efectivamente_usado>",
            "usage": { // Opcional, información de uso/costo
              "total_tokens": 123,
              "prompt_tokens": 123
            }
          },
          "error": null
        }
        ```
        *Explicación de Campos Clave (Respuesta)*:
          *   `data.embeddings`: Lista de listas de floats, donde cada sublista es el vector de embedding para el texto correspondiente en la solicitud.
          *   `data.model_used`: Nombre del modelo de embedding que ES utilizó para generar los vectores.
          *   `data.usage`: (Opcional pero recomendado) Información sobre el uso de tokens, útil para monitorización y facturación.
*   **Estado de Implementación**: Implementado en el cliente AES. Se asume implementado en ES. (Verificado en `EmbeddingClient.generate_embeddings_sync`).
*   **Análisis Crítico y Observaciones Clave**:
    *   **Redundancia de `correlation_id`**: Similar a otras interacciones, el `correlation_id` está duplicado. Debería estar solo a nivel raíz.
    *   **Especificación del Modelo**: La capacidad de especificar un `model` en la solicitud es importante. Si no se especifica, ES debe tener una lógica clara para seleccionar el modelo (ej. por defecto del tenant, o basado en `collection_id` si se provee y está asociado a un modelo específico).
    *   **Manejo de Errores**: AES debe manejar casos donde `success` es `false` (ej. modelo no disponible, error en ES, texto de entrada inválido).
    *   **Consistencia de la Cola de Respuesta**: El cliente AES espera la respuesta en `embedding:responses:generate:{correlation_id}`. ES debe enviar la respuesta a esta cola.
    *   **Callbacks Asíncronos (`embedding.callback`)**: El `ExecutionWorker` de AES también escucha en `embedding:callbacks:{tenant_id}:{session_id}`. Sin embargo, el método `generate_embeddings_sync` del cliente no utiliza este mecanismo de callback para su respuesta principal; espera directamente en la cola de respuesta síncrona. El propósito de este callback debe clarificarse: ¿es para un flujo alternativo asíncrono no utilizado por `generate_embeddings_sync`? ¿O es un remanente de un diseño anterior? Si AES necesita embeddings de forma asíncrona para tareas largas, podría haber un método `generate_embeddings_async` que sí utilice este callback.
    *   **Información de `usage`**: Incluir `usage` (tokens) en la respuesta es una buena práctica para la observabilidad y gestión de costos.

##### Interacción 2.1.5: `AES -> Query Service (QS): Generar Respuesta RAG (Síncrono)`

*   **Contexto y Justificación Detallada**: Para enriquecer las respuestas de los agentes con información de bases de conocimiento (Retrieval Augmented Generation - RAG), AES consulta al Query Service. Este servicio busca información relevante en las colecciones vectoriales y la devuelve para que el LLM la utilice.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.query_client.QueryClient.generate_rag_sync()`.
*   **Destino (Servidor)**: `Query Service`, procesado por `query_service.workers.query_worker.QueryWorker` (utilizando `query_service.handlers.query_handler.QueryHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `query.rag.sync`
    *   Cola de Solicitud: `query.actions` (El `DomainQueueManager` puede añadir prefijos/sufijos basados en `tenant_id`).
    *   Patrón de Cola de Respuesta: `query:responses:generate:{correlation_id}`
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud** (basado en el cliente AES y la lógica común):
        ```json
        {
          "action_id": "<uuid4>",
          "action_type": "query.rag.sync",
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_contextual>", // Para logging/tracking
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "query": "¿Cuál es la política de devoluciones?",
            "model_name": "<nombre_del_modelo_llm_del_agente>", // ej. "openai/gpt-4-turbo"
            "collections": [
              {
                "collection_id": "<uuid_collection_1>",
                "embedding_model": "<modelo_embedding_col_1>", // ej. "openai/text-embedding-ada-002"
                "top_k": 5,
                "metadata_filter": { "department": "sales" } // Opcional
              },
              {
                "collection_id": "<uuid_collection_2>",
                "embedding_model": "<modelo_embedding_col_2>",
                "top_k": 3
              }
            ],
            "temperature": 0.0, // Para re-ranking o generación interna en QS si aplica
            "max_tokens": 500, // Para generación interna en QS si aplica
            "metadata": { /* metadatos adicionales para logging o contexto */ },
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado aquí
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `data.query`: La pregunta o consulta del usuario/agente.
          *   `data.model_name`: El modelo LLM que utilizará la información. QS podría usarlo para adaptar la búsqueda o el formato de los resultados.
          *   `data.collections`: Lista de colecciones sobre las que buscar. Cada una especifica `collection_id`, el `embedding_model` (CRÍTICO: debe coincidir con el usado para los datos en esa colección), `top_k` (cuántos resultados obtener), y un `metadata_filter` opcional.
          *   `correlation_id` (raíz y en `data`): Usado por AES para esperar la respuesta. Redundante en `data`.

    *   **Payload de Respuesta (Esperado por AES)**:
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "results": [
              {
                "collection_id": "<uuid_collection_1>",
                "documents": [
                  {
                    "document_id": "<doc_1_id>",
                    "text": "Texto del documento relevante 1...",
                    "score": 0.89,
                    "metadata": { /* metadatos del documento original */ }
                  },
                  { 
                    "document_id": "<doc_2_id>",
                    "text": "Texto del documento relevante 2...",
                    "score": 0.85,
                    "metadata": { /* metadatos del documento original */ }
                  }
                ]
              },
              {
                "collection_id": "<uuid_collection_2>",
                "documents": [ /* ... documentos de la colección 2 ... */ ]
              }
            ],
            "raw_query_response": { /* Respuesta original del motor de búsqueda vectorial si es relevante */ }
          },
          "error": null
        }
        ```
        *Explicación de Campos Clave (Respuesta)*:
          *   `data.results`: Lista de resultados, agrupados por `collection_id` de la solicitud.
          *   `data.results[].documents`: Lista de documentos recuperados para esa colección, cada uno con su `document_id`, `text` (contenido), `score` de relevancia, y `metadata` original.
*   **Estado de Implementación**: Implementado en el cliente AES. Se asume implementado en QS. (Verificado en `QueryClient.generate_rag_sync`).
*   **Análisis Crítico y Observaciones Clave**:
    *   **Redundancia de `correlation_id`**: Misma observación que en interacciones previas.
    *   **CRÍTICO: `embedding_model` por Colección**: Es absolutamente vital que AES envíe el `embedding_model` correcto para CADA colección en la solicitud. QS usará este modelo para generar el embedding de la `data.query` y compararlo con los vectores de la colección. Si el modelo no coincide con el que se usó para indexar los datos de la colección, los resultados de la búsqueda serán incorrectos o sin sentido.
    *   **Fuente de `embedding_model`**: AES obtiene esta información de la configuración del agente (proveniente de AMS). Esto subraya la importancia de que AMS devuelva una configuración de agente completa y precisa.
    *   **Manejo de Errores**: AES debe manejar errores como colecciones no encontradas, modelos de embedding no válidos, o fallos internos en QS.
    *   **Consistencia de la Cola de Respuesta**: QS debe responder a `query:responses:generate:{correlation_id}`.
    *   **Callbacks Asíncronos (`query.callback`)**: Similar a EmbeddingService, `ExecutionWorker` en AES escucha en `query:callbacks:{tenant_id}:{session_id}`. El método `generate_rag_sync` no usa este callback para su respuesta principal. Su propósito necesita clarificación (flujo asíncrono alternativo, legado, etc.).
    *   **Complejidad del Payload de Solicitud**: El payload es bastante rico, permitiendo búsquedas en múltiples colecciones con diferentes parámetros. Esto ofrece flexibilidad pero también requiere una correcta construcción por parte de AES.
    *   **Formato de Resultados**: El formato de `data.results` agrupado por colección es lógico y facilita a AES procesar los contextos recuperados.

## 2.2 Comunicaciones Entrantes a AgentExecutionService (AES)

Esta sección detalla los mensajes y acciones que el AgentExecutionService recibe de otros servicios. Principalmente se trata de callbacks o respuestas asíncronas a solicitudes que AES pudo haber iniciado.

### Interacción 2.2.1: `Embedding Service (ES) -> AES: Callback de Generación de Embeddings`

*   **Contexto y Justificación Detallada**: Aunque AES tiene un método `generate_embeddings_sync` que espera una respuesta directa, el `ExecutionWorker` de AES también está configurado para escuchar en colas de callback del Embedding Service. Este callback podría ser utilizado por ES para notificar a AES sobre la finalización (exitosa o con error) de una tarea de generación de embeddings que fue iniciada de forma que no requería una espera síncrona por parte del solicitante original dentro de AES, o para proporcionar información adicional/actualizaciones.
*   **Iniciador (Servidor que envía el callback)**: `Embedding Service`, presumiblemente `embedding_service.workers.embedding_worker.EmbeddingWorker`.
*   **Destino (Cliente que recibe el callback)**: `Agent Execution Service`, específicamente `agent_execution_service.workers.execution_worker.ExecutionWorker` (manejado en su método `_handle_action`).
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `embedding.callback` (Inferido, debe ser confirmado. El worker AES escucha en la cola, pero el `action_type` específico del mensaje de callback debe ser definido por ES).
    *   Cola de Escucha (en AES): `embedding:callbacks:{tenant_id}:{session_id}` (Patrón de cola donde `{tenant_id}` y `{session_id}` son provistos dinámicamente, probablemente originados en la solicitud inicial a ES).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Callback (Enviado por ES a AES)** (Ejemplo Hipotético):
        ```json
        {
          "action_id": "<uuid4_accion_callback>",
          "action_type": "embedding.callback", 
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_original>",
          "correlation_id": "<uuid_correlacion_solicitud_original_si_existe>", // ID de la solicitud original a ES si es relevante para este callback
          "timestamp": "<iso_timestamp_callback>",
          "data": {
            "status": "completed", // o "failed"
            "original_request_data": { // Opcional, para dar contexto
              "texts_count": 2,
              "model_requested": "openai/text-embedding-ada-002"
            },
            "embeddings": [
              [0.001, 0.002, ..., -0.005],
              [-0.003, 0.004, ..., 0.001]
            ], // Presente si status es "completed"
            "model_used": "<nombre_del_modelo_efectivamente_usado>", // Presente si status es "completed"
            "usage": { "total_tokens": 123, "prompt_tokens": 123 }, // Presente si status es "completed"
            "error_message": "Modelo no encontrado", // Presente si status es "failed"
            "error_details": { /* ... detalles del error ... */ } // Presente si status es "failed"
          }
        }
        ```
        *Explicación de Campos Clave (Callback)*:
          *   `session_id`: Crucial para que AES enrute internamente este callback al contexto de ejecución correcto si es necesario.
          *   `correlation_id`: Si el flujo de callback está pensado para correlacionarse con una solicitud síncrona previa que también usó un `correlation_id` para su respuesta directa, este campo ayudaría a AES a vincularlos. Sin embargo, el propósito principal de los callbacks suele ser para operaciones puramente asíncronas.
          *   `data.status`: Indica el resultado de la operación de embedding.
          *   `data.embeddings`, `data.model_used`, `data.usage`: Misma estructura que en la respuesta síncrona si la operación fue exitosa.
          *   `data.error_message`, `data.error_details`: Información del error si la operación falló.

*   **Estado de Implementación**:
    *   Lado AES: El `ExecutionWorker` está configurado para escuchar en la cola `embedding:callbacks:{tenant_id}:{session_id}`.
    *   Lado ES: Se desconoce si ES actualmente envía mensajes a esta cola de callback y con qué `action_type` o payload. El flujo síncrono `embedding.generate.sync` no parece depender de este callback para su funcionamiento.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Propósito del Callback**: El uso exacto de este mecanismo de callback no está claro, dado que `generate_embeddings_sync` en AES es bloqueante y espera una respuesta directa. Posibles usos:
        *   Para un flujo de generación de embeddings totalmente asíncrono (ej. `generate_embeddings_async` que AES podría invocar y luego continuar, esperando el resultado vía este callback).
        *   Para notificaciones secundarias (ej. auditoría, logging extendido) incluso después de una respuesta síncrona.
        *   Legado: Podría ser un remanente de un diseño anterior.
    *   **`action_type` del Callback**: El `action_type` específico que ES usaría en el mensaje de callback (ej. `embedding.callback` o `embedding.generate.completed`) necesita ser definido y conocido por el `ExecutionWorker` de AES para su correcto manejo.
    *   **Contenido del Payload del Callback**: El payload debe ser suficientemente informativo para que AES pueda actuar en consecuencia (ej. obtener los embeddings, registrar un error, notificar a otro componente).
    *   **Correlación**: Si estos callbacks se relacionan con solicitudes previas, el `correlation_id` de la solicitud original debería incluirse en el payload del callback para permitir a AES asociar el callback con la tarea que lo originó.
    *   **Necesidad de Documentación en ES**: La documentación de Embedding Service debería detallar cuándo y cómo utiliza estas colas de callback.

### Interacción 2.2.2: `Query Service (QS) -> AES: Callback de Generación de Respuesta RAG`

*   **Contexto y Justificación Detallada**: De forma análoga al Embedding Service, aunque AES utiliza `generate_rag_sync` para obtener resultados RAG de manera bloqueante, el `ExecutionWorker` de AES también escucha en colas de callback del Query Service. Este mecanismo podría usarse para notificar a AES sobre la finalización de una tarea RAG asíncrona o para enviar actualizaciones.
*   **Iniciador (Servidor que envía el callback)**: `Query Service`, presumiblemente `query_service.workers.query_worker.QueryWorker`.
*   **Destino (Cliente que recibe el callback)**: `Agent Execution Service`, específicamente `agent_execution_service.workers.execution_worker.ExecutionWorker` (manejado en su método `_handle_action`).
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `query.callback` (Inferido, debe ser confirmado. El worker AES escucha en la cola, pero el `action_type` específico del mensaje de callback debe ser definido por QS).
    *   Cola de Escucha (en AES): `query:callbacks:{tenant_id}:{session_id}` (Patrón de cola donde `{tenant_id}` y `{session_id}` son provistos dinámicamente, originados en la solicitud inicial a QS).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Callback (Enviado por QS a AES)** (Ejemplo Hipotético):
        ```json
        {
          "action_id": "<uuid4_accion_callback>",
          "action_type": "query.callback", 
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_original>",
          "correlation_id": "<uuid_correlacion_solicitud_original_si_existe>",
          "timestamp": "<iso_timestamp_callback>",
          "data": {
            "status": "completed", // o "failed"
            "original_request_data": { // Opcional
              "query": "¿Cuál es la política de devoluciones?",
              "collections_queried_count": 2
            },
            "results": [ // Presente si status es "completed"
              {
                "collection_id": "<uuid_collection_1>",
                "documents": [
                  {
                    "document_id": "<doc_1_id>",
                    "text": "Texto del documento relevante 1...",
                    "score": 0.89,
                    "metadata": { /* metadatos del documento original */ }
                  }
                ]
              }
            ],
            "raw_query_response": { /* ... */ }, // Presente si status es "completed"
            "error_message": "Colección no encontrada", // Presente si status es "failed"
            "error_details": { /* ... detalles del error ... */ } // Presente si status es "failed"
          }
        }
        ```
        *Explicación de Campos Clave (Callback)*:
          *   `session_id`: Para enrutamiento interno en AES.
          *   `correlation_id`: Para vincular con una solicitud original si aplica.
          *   `data.status`: Resultado de la operación RAG.
          *   `data.results`: Misma estructura que en la respuesta síncrona si la operación fue exitosa.
          *   `data.error_message`, `data.error_details`: Información del error si falló.

*   **Estado de Implementación**:
    *   Lado AES: El `ExecutionWorker` está configurado para escuchar en la cola `query:callbacks:{tenant_id}:{session_id}`.
    *   Lado QS: Se desconoce si QS actualmente envía mensajes a esta cola de callback y con qué `action_type` o payload. El flujo síncrono `query.rag.sync` no parece depender de este callback.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Propósito del Callback**: Similar al callback de ES, su uso no está claro dado el método síncrono `generate_rag_sync`. Podría ser para flujos RAG asíncronos, notificaciones secundarias, o ser un remanente.
    *   **`action_type` del Callback**: El `action_type` específico que QS usaría (ej. `query.callback` o `query.rag.completed`) necesita ser definido y manejado por AES.
    *   **Contenido del Payload del Callback**: Debe ser suficiente para que AES procese el resultado o el error.
    *   **Correlación**: Importante si se relaciona con solicitudes previas.
    *   **Necesidad de Documentación en QS**: La documentación de Query Service debe aclarar el uso de estas colas de callback.

# 3. Agent Management Service (AMS)

El Agent Management Service (AMS) es responsable de la creación, configuración, y gestión del ciclo de vida de los agentes conversacionales y sus plantillas. Proporciona la configuración detallada que otros servicios, como AES, necesitan para ejecutar agentes.

## 3.1 Comunicaciones Salientes desde AgentManagementService (AMS)

Esta sección describe las interacciones que AMS inicia hacia otros servicios.

### Interacción 3.1.1: `AMS -> Ingestion Service (IS): Iniciar Ingesta de Documentos para Colección`

*   **Contexto y Justificación Detallada**: Cuando un usuario crea o actualiza un agente en AMS y asocia nuevas fuentes de datos a una colección (ej. URLs, archivos), AMS necesita instruir al Ingestion Service (IS) para que procese estos documentos. IS se encargará de obtener, fragmentar y preparar estos documentos para su posterior uso en búsquedas RAG.
*   **Iniciador (Cliente)**: `Agent Management Service`, probablemente desde un handler o servicio interno que gestiona la lógica de creación/actualización de agentes y colecciones (ej. `agent_management_service.services.collection_service`).
*   **Destino (Servidor)**: `Ingestion Service`, procesado por `ingestion_service.workers.ingestion_worker.IngestionWorker` (utilizando `ingestion_service.handlers.ingestion_handler.IngestionHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono para la aceptación de la tarea, con procesamiento de ingesta real ocurriendo de forma asíncrona (IS podría usar WebSockets o callbacks para notificar el progreso/finalización, como se mencionó en su documentación).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `ingestion.process_sources` (o similar, ej. `ingestion.start_collection_ingestion`)
    *   Cola de Solicitud: `ingestion.actions` (El `DomainQueueManager` puede añadir prefijos/sufijos basados en `tenant_id`).
    *   Patrón de Cola de Respuesta (para aceptación de tarea): `ingestion:responses:process_sources:{correlation_id}`
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Enviado por AMS a IS)**:
        ```json
        {
          "action_id": "<uuid4>",
          "action_type": "ingestion.process_sources",
          "tenant_id": "<id_del_tenant>",
          "correlation_id": "<uuid_para_correlacion_respuesta_aceptacion>",
          "timestamp": "<iso_timestamp>",
          "data": {
            "collection_id": "<uuid_de_la_coleccion>",
            "embedding_model_name": "<nombre_modelo_embedding_para_la_coleccion>", // ej. "openai/text-embedding-ada-002"
            "documents": [
              { "type": "url", "source": "https://example.com/doc1", "document_id_hint": "<opcional_id_doc_1>" },
              { "type": "file_path", "source": "/path/to/tenant_files/doc2.pdf", "document_id_hint": "<opcional_id_doc_2>" },
              { "type": "raw_text", "source": "Este es un texto plano para ingestar.", "document_id_hint": "<opcional_id_doc_3>", "metadata": {"title": "Texto Plano 1"} }
            ],
            "processing_config": { // Opcional, configuraciones específicas de ingesta
              "chunk_size": 1000,
              "chunk_overlap": 100,
              "use_ocr_for_pdfs": true
            },
            "metadata_default": { // Metadatos a aplicar a todos los documentos de esta ingesta si no tienen el suyo
                "agent_id": "<uuid_agente_asociado>"
            },
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta_aceptacion>" // Duplicado
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud)*:
          *   `data.collection_id`: Identificador de la colección a la que pertenecen los documentos.
          *   `data.embedding_model_name`: Modelo de embedding asociado a la colección. IS puede necesitarlo para estrategias de chunking optimizadas para ese modelo.
          *   `data.documents`: Lista de fuentes de datos a ingestar, cada una con su tipo (`url`, `file_path`, `raw_text`), la fuente en sí, y un `document_id_hint` opcional que IS podría usar o generar uno nuevo.
          *   `data.processing_config`: Configuraciones opcionales para guiar el proceso de chunking y extracción de texto en IS.
          *   `data.metadata_default`: Metadatos que se pueden aplicar por defecto a los documentos procesados.

    *   **Payload de Respuesta (Aceptación de Tarea, Esperado por AMS de IS)**:
        ```json
        {
          "success": true, // boolean: indica si IS aceptó la tarea de ingesta
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "ingestion_task_id": "<uuid_tarea_de_ingesta_en_is>",
            "message": "Tarea de ingesta para la colección <uuid_collection> recibida y encolada.",
            "estimated_completion_time": null // IS podría no saberlo en este punto
          },
          "error": null // string: mensaje de error si success es false (ej. payload inválido, tenant sin permisos)
        }
        ```
        *Explicación de Campos Clave (Respuesta de Aceptación)*:
          *   `success`: Indica si IS ha validado y aceptado la solicitud de ingesta.
          *   `data.ingestion_task_id`: Un ID que AMS podría usar para rastrear el progreso de la ingesta a través de otros mecanismos (ej. WebSockets, consultando un endpoint de estado en IS).
*   **Estado de Implementación**: Conceptual. La implementación real dependerá de las capacidades existentes en AMS e IS.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Comunicación de Progreso/Finalización**: La respuesta síncrona es solo para la aceptación. El progreso real y la finalización de la ingesta (que puede ser larga) deben comunicarse de forma asíncrona (ej. IS emitiendo eventos `ingestion.document.processed`, `ingestion.collection.completed` o usando WebSockets como se mencionó en la documentación de IS).
    *   **Manejo de Archivos**: Si `type` es `file_path`, se debe definir cómo AMS e IS acceden a estos archivos (ej. almacenamiento compartido, AMS sube el archivo a una ubicación temporal accesible por IS).
    *   **Idempotencia**: IS debería manejar reintentos de la misma solicitud de ingesta de forma idempotente, posiblemente usando `collection_id` y `document_id_hint`.
    *   **Error Handling Detallado**: Los errores durante el proceso de ingesta (documento no accesible, formato no soportado) deben ser registrados por IS y, idealmente, comunicados de vuelta a AMS o a un sistema de monitorización.
    *   **Seguridad y Acceso a Datos**: Asegurar que IS solo acceda a datos permitidos para el `tenant_id` especificado.
    *   **Dependencia de `embedding_model_name`**: Aunque IS no genera embeddings directamente (eso lo hace ES), conocer el `embedding_model_name` puede ser crucial para el chunking, ya que diferentes modelos tienen diferentes tamaños de contexto y óptimos de tokenización.
    *   **Actualización de Estado en AMS**: AMS, tras recibir la confirmación de aceptación, debería marcar la colección o los documentos como "en proceso de ingesta". Luego, mediante los mecanismos asíncronos de IS, actualizaría el estado a "ingestado" o "fallido".

## 3.2 Comunicaciones Entrantes a AgentManagementService (AMS)

Esta sección describe las interacciones que AMS recibe de otros servicios. La principal es la solicitud de configuraciones de agente por parte de AES.

### Interacción 3.2.1: `Agent Execution Service (AES) -> AMS: Obtener Configuración de Agente`

*   **Contexto y Justificación Detallada**: Para ejecutar un agente, AES necesita su configuración completa, incluyendo el modelo LLM, herramientas, prompt del sistema, y detalles de las colecciones RAG asociadas (con sus respectivos modelos de embedding). AMS es la fuente autoritativa de esta información.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.management_client.AgentManagementClient.get_agent_config()`.
*   **Destino (Servidor)**: `Agent Management Service`, procesado por `agent_management_service.workers.management_worker.ManagementWorker` (utilizando `agent_management_service.handlers.management_handler.ManagementHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `agent.get_config_for_slug` (o `agent.get_config` si se usa ID de agente directamente).
    *   Cola de Solicitud (Escuchada por AMS): `management.actions` (o `management:{tenant_id}:actions` si está particionada y el `DomainQueueManager` de AES la resuelve correctamente).
    *   Patrón de Cola de Respuesta (Usada por AMS para responder): `management:responses:get_config:{correlation_id}` (El cliente AES espera en esta cola).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Recibido por AMS de AES)** (Corresponde a la Interacción 2.1.1):
        ```json
        {
          "action_id": "<uuid4>",
          "action_type": "agent.get_config_for_slug",
          "tenant_id": "<id_del_tenant_en_data>", // Presente en 'data', AMS debe usarlo.
          "session_id": "<id_de_sesion_aes>", // Para contexto/logging
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "agent_slug": "<slug_del_agente>",
            "tenant_id": "<id_del_tenant>", // Reafirmación del tenant_id
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado
          }
        }
        ```
        *Consideraciones para AMS al Procesar la Solicitud*:
          *   AMS debe usar `data.agent_slug` y `data.tenant_id` para localizar la configuración del agente.
          *   Debe asegurar que el `tenant_id` tiene acceso al agente solicitado.

    *   **Payload de Respuesta (Enviado por AMS a AES)** (Corresponde a la Interacción 2.1.1):
        ```json
        {
          "success": true, // boolean: indica si la operación fue exitosa
          "correlation_id": "<mismo_uuid_de_la_solicitud>", // Esencial para AES
          "data": {
            "agent_config": {
              "agent_id": "<uuid_del_agente>",
              "name": "Nombre del Agente",
              "system_prompt": "Este es el prompt del sistema...",
              "model_name": "proveedor/modelo-llm",
              "temperature": 0.7,
              "max_tokens": 1024,
              "tools": [ /* ... lista de herramientas ... */ ],
              "collections": [
                { 
                  "collection_id": "<uuid_collection_1>", 
                  "name": "Nombre Colección 1",
                  "embedding_model": "proveedor/modelo-embedding-col-1"
                }
                // ... más colecciones
              ],
              "metadata": { /* ... */ },
              "tier_config": { /* ... */ }
            }
          },
          "error": null // string: mensaje de error si success es false
        }
        ```
        *Consideraciones para AMS al Enviar la Respuesta*:
          *   El campo `agent_config` debe ser **exhaustivo**. Es CRÍTICO que incluya todos los detalles necesarios para AES, especialmente la lista de `collections` con sus `collection_id` y los `embedding_model` específicos para cada una.
          *   El `correlation_id` debe ser el mismo que el de la solicitud.
          *   La respuesta debe ser enviada a la cola `management:responses:get_config:{correlation_id}`.
*   **Estado de Implementación**: Implementado en AMS (worker/handler) y en el cliente AES.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva AMS)**:
    *   **Fuente de Verdad**: AMS actúa como la fuente de verdad para las configuraciones de agentes. La integridad y completitud de los datos que sirve son fundamentales para el funcionamiento de AES.
    *   **Validación y Seguridad**: AMS debe validar que el `tenant_id` solicitante tiene permiso para acceder a la configuración del agente (basado en `agent_slug` o `agent_id`).
    *   **Rendimiento y Caché**: Dado que esta es una solicitud frecuente, AMS podría implementar mecanismos de caché (como se menciona en su documentación, ej. Redis) para las configuraciones de agentes y así reducir la latencia y la carga en su base de datos principal (PostgreSQL).
    *   **Manejo de Errores**: Si el agente no se encuentra, o el tenant no tiene acceso, AMS debe devolver `success: false` con un mensaje de error claro.
    *   **Consistencia del `embedding_model` en Colecciones**: AMS es responsable de asegurar que la configuración de cada colección dentro de un agente incluya el `embedding_model` correcto. Este dato es vital para que AES pueda interactuar adecuadamente con QS.

# 4. Conversation Service (CS)

El Conversation Service (CS) es el encargado de almacenar y recuperar el historial de interacciones (mensajes) dentro de una sesión de conversación entre un usuario y un agente. Es fundamental para mantener el contexto a lo largo de múltiples turnos.

## 4.1 Comunicaciones Entrantes a ConversationService (CS)

Esta sección describe las interacciones que CS recibe de otros servicios, principalmente de AES.

### Interacción 4.1.1: `Agent Execution Service (AES) -> CS: Obtener Historial de Conversación`

*   **Contexto y Justificación Detallada**: Antes de que AES pueda generar una respuesta de agente, necesita el historial de la conversación actual para proporcionar contexto al modelo LLM. AES solicita este historial a CS.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.conversation_client.ConversationClient.get_conversation_history()`.
*   **Destino (Servidor)**: `Conversation Service`, procesado por su worker y handler correspondiente (ej. `conversation_service.workers.conversation_worker.ConversationWorker` y `conversation_service.handlers.conversation_handler.ConversationHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `conversation.get_history`.
    *   Cola de Solicitud (Escuchada por CS): `conversation.actions` (o similar, dependiendo de la configuración del `DomainQueueManager`).
    *   Patrón de Cola de Respuesta (Usada por CS para responder): `conversation:responses:get_history:{correlation_id}` (El cliente AES espera en esta cola).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Recibido por CS de AES)** (Corresponde a la Interacción 2.1.2):
        ```json
        {
          "action_id": "<uuid4_accion>",
          "action_type": "conversation.get_history",
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_para_obtener_historial>", // También en 'data'
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "tenant_id": "<id_del_tenant>",
            "session_id": "<id_de_sesion_para_obtener_historial>",
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>",
            "limit": 20, // Opcional, cuántos mensajes traer
            "offset": 0 // Opcional, para paginación
          }
        }
        ```
        *Consideraciones para CS al Procesar la Solicitud*:
          *   CS debe usar `data.session_id` y `data.tenant_id` para filtrar y recuperar los mensajes correctos.
          *   Debe aplicar `limit` y `offset` si se proveen.
          *   Validar que el `tenant_id` tiene acceso a la `session_id` (aunque esto es más una cuestión de pertenencia).

    *   **Payload de Respuesta (Enviado por CS a AES)** (Corresponde a la Interacción 2.1.2):
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "history": [
              {
                "message_id": "<uuid_mensaje_1>",
                "role": "user", // "user", "assistant", "system"
                "content": "Hola, ¿cómo estás?",
                "timestamp": "<iso_timestamp_mensaje_1>",
                "metadata": { /* metadatos adicionales del mensaje */ }
              },
              {
                "message_id": "<uuid_mensaje_2>",
                "role": "assistant",
                "content": "Estoy bien, ¿cómo puedo ayudarte?",
                "timestamp": "<iso_timestamp_mensaje_2>",
                "metadata": { "llm_model_used": "openai/gpt-3.5-turbo" }
              }
              // ... más mensajes
            ],
            "total_messages_in_session": 50, // Opcional, útil para paginación
            "limit": 20,
            "offset": 0
          },
          "error": null
        }
        ```
        *Consideraciones para CS al Enviar la Respuesta*:
          *   La lista `history` debe contener los mensajes en el orden correcto (generalmente cronológico ascendente).
          *   Cada mensaje debe tener una estructura consistente.
          *   El `correlation_id` debe ser el mismo que el de la solicitud.
          *   La respuesta debe ser enviada a la cola `conversation:responses:get_history:{correlation_id}`.
          *   **CRÍTICO**: Verificar la consistencia del nombre de la cola de respuesta. Previamente se observó una posible inconsistencia (`conversation:responses:{correlation_id}` vs `conversation:responses:get_history:{correlation_id}`). Debe ser estandarizado y CS debe usar el patrón correcto que el cliente espera.

*   **Estado de Implementación**: Implementado en CS (worker/handler) y en el cliente AES.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva CS)**:
    *   **Persistencia**: CS es responsable de la persistencia a largo plazo de los mensajes. Actualmente usa Redis, pero hay planes de migrar a PostgreSQL (ver memorias).
    *   **Integridad de Datos**: Asegurar que los mensajes se almacenen y recuperen sin corrupción y asociados al `tenant_id` y `session_id` correctos.
    *   **Paginación y Límites**: Implementar correctamente la paginación (`limit`, `offset`) para manejar conversaciones largas de manera eficiente.
    *   **Rendimiento**: La recuperación del historial debe ser rápida, ya que es un paso crítico en cada turno de conversación. El uso de índices adecuados en la base de datos (cuando se migre a PostgreSQL) será crucial.
    *   **Manejo de Errores**: Si la sesión no se encuentra, o hay un problema al acceder a los datos, CS debe devolver `success: false` con un mensaje de error apropiado.
    *   **Filtrado y Formato**: CS podría ofrecer opciones de filtrado adicionales en el futuro (ej. por rango de fechas, por tipo de rol) o diferentes formatos de historial (ej. formato LangChain `BaseMessage`).

### Interacción 4.1.2: `Agent Execution Service (AES) -> CS: Guardar Mensaje en Conversación`

*   **Contexto y Justificación Detallada**: Después de que un usuario envía un mensaje o el agente genera una respuesta, AES necesita persistir estos mensajes en el historial de la conversación. AES envía el mensaje a CS para su almacenamiento.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.conversation_client.ConversationClient.save_message()`.
*   **Destino (Servidor)**: `Conversation Service`, procesado por su worker y handler (ej. `conversation_service.workers.conversation_worker.ConversationWorker` y `conversation_service.handlers.conversation_handler.ConversationHandler`).
*   **Patrón de Comunicación**: Asíncrono (Fire-and-Forget desde la perspectiva de AES). CS recibe la acción y la procesa sin enviar una respuesta de confirmación directa a una cola de respuesta específica de la solicitud.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `conversation.save_message`.
    *   Cola de Solicitud (Escuchada por CS): `conversation.actions` (o similar).
    *   Cola de Respuesta: No se utiliza para confirmación síncrona en este patrón.
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicit งวด (Recibido por CS de AES)** (Corresponde a la Interacción 2.1.3):
        ```json
        {
          "action_id": "<uuid4_accion>",
          "action_type": "conversation.save_message",
          "tenant_id": "<id_del_tenant>",
          "session_id": "<id_de_sesion_donde_guardar>", // También en 'data'
          "correlation_id": "<uuid_opcional_para_logging_o_rastreo_asincrono>", // También en 'data', aunque no se espera respuesta directa
          "timestamp": "<iso_timestamp_envio>",
          "data": {
            "tenant_id": "<id_del_tenant>",
            "session_id": "<id_de_sesion_donde_guardar>",
            "correlation_id": "<mismo_uuid_opcional>",
            "message": {
              "message_id": "<uuid_del_mensaje_generado_por_aes_o_cliente>",
              "role": "user", // "user", "assistant", "system"
              "content": "Este es el contenido del mensaje a guardar.",
              "timestamp": "<iso_timestamp_creacion_mensaje>", // Puede diferir del timestamp de envío
              "metadata": {
                "llm_model_used": "openai/gpt-4", // Ejemplo si es 'assistant'
                "user_agent": "WebApp v1.2", // Ejemplo si es 'user'
                "language": "es"
              }
            }
          }
        }
        ```
        *Consideraciones para CS al Procesar la Solicitud*:
          *   CS debe extraer el objeto `message` de `data` y almacenarlo asociado al `data.tenant_id` y `data.session_id`.
          *   Debe manejar la persistencia del mensaje completo, incluyendo `message_id`, `role`, `content`, `timestamp` y `metadata`.
          *   El `message_id` es proporcionado por el cliente (AES). CS debe considerar si necesita validar su unicidad dentro de la sesión o si confía en el cliente.

*   **Estado de Implementación**: Implementado en CS (worker/handler) y en el cliente AES.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva CS)**:
    *   **Asincronía y Fiabilidad**: Al ser fire-and-forget, CS debe tener un mecanismo robusto para procesar estos mensajes. Si CS falla al procesar un mensaje, este podría perderse sin que AES lo sepa directamente. Se requieren logs detallados y posiblemente un sistema de reintentos o dead-letter queue en CS.
    *   **Idempotencia**: Si AES reenvía el mismo mensaje (ej. por un reintento a nivel de AES), CS debería idealmente manejarlo de forma idempotente, evitando duplicados. Usar el `message_id` proporcionado por el cliente para la detección de duplicados es una estrategia común.
    *   **Orden de Mensajes**: CS debe asegurar que los mensajes se almacenen de una manera que permita recuperarlos en el orden correcto, típicamente usando el `timestamp` del mensaje.
    *   **Validación de Datos**: CS debería validar el payload del mensaje (ej. campos requeridos, formato del `timestamp`).
    *   **Escalabilidad**: El guardado de mensajes puede ser una operación de alta frecuencia. La solución de persistencia de CS debe ser capaz de manejar la carga.
    *   **Consistencia Eventual**: Dado el patrón asíncrono, puede haber una pequeña demora entre que AES envía el mensaje y este está disponible para ser leído a través de `conversation.get_history`. Esto es típico en sistemas con consistencia eventual.
    *   **Error Handling y Notificación**: Aunque no hay respuesta síncrona, CS debe loguear errores exhaustivamente. Para errores críticos (ej. incapacidad persistente de guardar mensajes), se necesitarían mecanismos de alerta para los administradores del sistema.

# 5. Embedding Service (ES)

El Embedding Service (ES) es responsable de convertir fragmentos de texto en representaciones vectoriales numéricas (embeddings) utilizando modelos de lenguaje. Estos embeddings son cruciales para las búsquedas semánticas en sistemas RAG.

## 5.1 Comunicaciones Entrantes a EmbeddingService (ES)

Esta sección describe las interacciones que ES recibe de otros servicios, principalmente de AES para la generación de embeddings.

### Interacción 5.1.1: `Agent Execution Service (AES) -> ES: Generar Embeddings (Síncrono)`

*   **Contexto y Justificación Detallada**: Cuando AES necesita realizar una búsqueda semántica (parte de una consulta RAG) o cuando necesita generar embeddings para un nuevo contenido que se usará en el prompt, solicita a ES que genere estos embeddings para uno o más textos.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.embedding_client.EmbeddingClient.generate_embeddings_sync()`.
*   **Destino (Servidor)**: `Embedding Service`, procesado por `embedding_service.workers.embedding_worker.EmbeddingWorker` (a través de un `embedding_service.handlers.embedding_handler.EmbeddingHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `embedding.generate.sync`.
    *   Cola de Solicitud (Escuchada por ES): `embedding.actions`.
    *   Patrón de Cola de Respuesta (Usada por ES para responder): `embedding:responses:generate:{correlation_id}` (El cliente AES espera en esta cola).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Recibido por ES de AES)** (Corresponde a la Interacción 2.1.4):
        ```json
        {
          "action_id": "<uuid4_accion>",
          "action_type": "embedding.generate.sync",
          "tenant_id": "<id_del_tenant>",
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "texts": ["texto 1 para embeber", "otro texto más largo"],
            "model": "openai/text-embedding-ada-002", // Opcional, ES puede tener un default por tenant/global
            "collection_id": "<uuid_coleccion_opcional>", // Para contexto, logging, o futuras optimizaciones
            "session_id": "<id_de_sesion_aes>", // Para contexto o logging
            "tenant_id": "<id_del_tenant>", // Reafirmación
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado
          }
        }
        ```
        *Consideraciones para ES al Procesar la Solicitud*:
          *   ES debe procesar la lista `data.texts`.
          *   Debe seleccionar el modelo de embedding: el especificado en `data.model`, o uno por defecto si no se provee (potencialmente basado en `tenant_id` o configuración global).
          *   Validar que el `tenant_id` tiene permiso para usar el modelo solicitado (si aplica la validación por tier).
          *   Manejar lotes de textos eficientemente.

    *   **Payload de Respuesta (Enviado por ES a AES)** (Corresponde a la Interacción 2.1.4):
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "embeddings": [
              [0.00123, -0.00456, ..., 0.00789], // Embedding para "texto 1 para embeber"
              [0.00987,  0.00654, ..., -0.00321]  // Embedding para "otro texto más largo"
            ],
            "model_used": "openai/text-embedding-ada-002", // Modelo que finalmente se usó
            "usage": { // Información de uso del modelo (ej. de OpenAI)
              "prompt_tokens": 150,
              "total_tokens": 150
            }
          },
          "error": null
        }
        ```
        *Consideraciones para ES al Enviar la Respuesta*:
          *   La lista `embeddings` debe corresponder en orden y número a los `texts` de la solicitud.
          *   `model_used` debe reflejar el modelo exacto que generó los embeddings.
          *   `usage` es importante para el seguimiento de costos y cuotas.
          *   El `correlation_id` debe ser el mismo que el de la solicitud.
          *   La respuesta se envía a `embedding:responses:generate:{correlation_id}`.

*   **Estado de Implementación**: Implementado en ES (worker/handler) y en el cliente AES.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva ES)**:
    *   **Integración con Modelos Externos**: ES encapsula la lógica para interactuar con proveedores de modelos de embedding (ej. OpenAI, HuggingFace). Debe manejar API keys, reintentos, y errores de estos servicios externos.
    *   **Caché**: Para optimizar costos y latencia, ES podría implementar una caché para los embeddings generados (como se menciona en su documentación). La clave de caché podría ser una combinación del texto y el nombre del modelo.
    *   **Manejo de Errores del Proveedor**: Si el proveedor del modelo (ej. OpenAI) devuelve un error, ES debe traducirlo en una respuesta de error apropiada para AES (ej. `success: false` y un mensaje en `error`).
    *   **Validación por Tier/Cuotas**: ES podría ser responsable de verificar si el `tenant_id` tiene permiso para usar ciertos modelos o si ha excedido alguna cuota de generación de embeddings.
    *   **Rendimiento y Escalabilidad**: La generación de embeddings puede ser intensiva. ES debe ser escalable para manejar picos de carga.
    *   **Consistencia del Modelo**: Asegurar que el modelo especificado (o el default) se use consistentemente.
    *   **Seguridad de API Keys**: Manejo seguro de las claves de API para los servicios de modelos externos.

## 5.2 Comunicaciones Salientes desde EmbeddingService (ES)

La principal comunicación saliente documentada para ES es el callback hacia AES, que se usa en escenarios donde AES no espera síncronamente.

### Interacción 5.2.1: `Embedding Service (ES) -> AES: Callback de Generación de Embeddings`

*   Esta interacción ya fue detallada desde la perspectiva de AES como receptor (Ver Interacción 2.2.1). Desde la perspectiva de ES como iniciador:
    *   **Contexto**: Si ES procesa una solicitud de `embedding.generate.async` (no documentada aún como entrante a ES, pero hipotética dada la existencia del callback) o si un flujo interno en ES necesita notificar a AES sobre embeddings generados.
    *   **Destino**: `Agent Execution Service`, cola `embedding:callbacks:{tenant_id}:{session_id}`.
    *   **Payload**: Como se describió en 2.2.1, incluyendo `status`, `embeddings`, `usage`, `correlation_id` (de la solicitud original a ES), etc.
    *   **Observación**: La documentación de ES debería clarificar cuándo y bajo qué circunstancias ES inicia estos callbacks. Si solo existe `embedding.generate.sync` como acción principal, el callback podría ser para notificaciones secundarias o un remanente de un diseño anterior.

# 6. Query Service (QS)

El Query Service (QS) es el motor de búsqueda semántica del sistema. Recibe consultas, las enriquece potencialmente con embeddings, busca en las colecciones de documentos (vector stores) y devuelve los resultados más relevantes para ser utilizados en flujos de Retrieval Augmented Generation (RAG).

## 6.1 Comunicaciones Entrantes a QueryService (QS)

Esta sección describe las interacciones que QS recibe, principalmente de AES, para realizar búsquedas RAG.

### Interacción 6.1.1: `Agent Execution Service (AES) -> QS: Generar Respuesta RAG (Síncrono)`

*   **Contexto y Justificación Detallada**: Para que un agente pueda responder preguntas basadas en conocimiento específico, AES necesita realizar una búsqueda RAG. AES envía la consulta del usuario y los detalles de las colecciones a QS, que se encarga de buscar la información relevante.
*   **Iniciador (Cliente)**: `Agent Execution Service`, específicamente `agent_execution_service.clients.query_client.QueryClient.generate_rag_sync()`.
*   **Destino (Servidor)**: `Query Service`, procesado por `query_service.workers.query_worker.QueryWorker` (a través de un `query_service.handlers.query_handler.QueryHandler`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `query.rag.sync`.
    *   Cola de Solicitud (Escuchada por QS): `query.actions`.
    *   Patrón de Cola de Respuesta (Usada por QS para responder): `query:responses:generate:{correlation_id}` (El cliente AES espera en esta cola).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Recibido por QS de AES)** (Corresponde a la Interacción 2.1.5):
        ```json
        {
          "action_id": "<uuid4_accion>",
          "action_type": "query.rag.sync",
          "tenant_id": "<id_del_tenant>",
          "correlation_id": "<uuid_para_correlacion_respuesta>", // También en 'data'
          "timestamp": "<iso_timestamp>",
          "data": {
            "query": "¿Cuál es la política de devoluciones?",
            "collections": [
              {
                "collection_id": "<uuid_collection_1>",
                "embedding_model": "openai/text-embedding-ada-002", // CRÍTICO: QS usa este modelo para generar el embedding de la query PARA ESTA COLECCIÓN
                "top_k": 5,
                "metadata_filter": { "category": "electronics" } // Opcional
              },
              {
                "collection_id": "<uuid_collection_2>",
                "embedding_model": "openai/text-embedding-3-large",
                "top_k": 3
              }
            ],
            "session_id": "<id_de_sesion_aes>", // Para contexto o logging
            "tenant_id": "<id_del_tenant>", // Reafirmación
            "correlation_id": "<mismo_uuid_para_correlacion_respuesta>" // Duplicado
          }
        }
        ```
        *Consideraciones para QS al Procesar la Solicitud*:
          *   QS debe iterar sobre cada elemento en `data.collections`.
          *   Para cada colección, QS (o más bien, el ES al que QS delegará) debe generar un embedding para `data.query` utilizando el `embedding_model` **específico** de esa colección.
          *   Luego, QS realiza la búsqueda en el vector store correspondiente a `collection_id` utilizando el embedding generado, `top_k` y `metadata_filter`.
          *   Validar que el `tenant_id` tiene acceso a las colecciones solicitadas.

    *   **Payload de Respuesta (Enviado por QS a AES)** (Corresponde a la Interacción 2.1.5):
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_de_la_solicitud>",
          "data": {
            "results_per_collection": [
              {
                "collection_id": "<uuid_collection_1>",
                "query_embedding_model_used": "openai/text-embedding-ada-002",
                "documents": [
                  {
                    "document_id": "<doc_1_id>",
                    "text": "Texto del documento relevante 1...",
                    "score": 0.89,
                    "metadata": { /* metadatos del documento original */ }
                  }
                  // ... más documentos para esta colección
                ]
              },
              {
                "collection_id": "<uuid_collection_2>",
                "query_embedding_model_used": "openai/text-embedding-3-large",
                "documents": [ /* ... */ ]
              }
            ],
            "raw_provider_responses": { /* Opcional: respuestas crudas de los vector stores si es útil */ }
          },
          "error": null
        }
        ```
        *Consideraciones para QS al Enviar la Respuesta*:
          *   `results_per_collection` debe ser una lista, donde cada elemento corresponde a una colección de la solicitud.
          *   Es crucial que `query_embedding_model_used` se reporte correctamente para cada colección.
          *   Los documentos deben incluir su contenido, score de similitud y metadatos.
          *   El `correlation_id` debe ser el mismo que el de la solicitud.
          *   La respuesta se envía a `query:responses:generate:{correlation_id}`.

*   **Estado de Implementación**: Implementado en QS (worker/handler) y en el cliente AES.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva QS)**:
    *   **Delegación de Embeddings**: QS no genera embeddings directamente. Cuando recibe una consulta, debe tomar el texto de la consulta (`data.query`) y, para cada colección especificada, solicitar al Embedding Service (ES) que genere un embedding para ese texto usando el `embedding_model` asociado a *esa colección específica*. Esta es una interacción QS -> ES no documentada explícitamente aún, pero implícita y crítica.
    *   **Integración con Vector Stores**: QS es el servicio que interactúa directamente con las bases de datos vectoriales (ej. Weaviate, Pinecone, ChromaDB). Debe manejar la configuración, conexión, y la sintaxis de consulta específica de cada vector store soportado.
    *   **Manejo de Múltiples Colecciones y Modelos**: La capacidad de consultar múltiples colecciones, cada una potencialmente usando un modelo de embedding diferente, es una característica poderosa pero compleja. QS debe manejar esto correctamente, asegurando que el embedding de la consulta se genere con el modelo correcto para cada búsqueda en colección.
    *   **Filtrado por Metadatos**: QS debe traducir los `metadata_filter` en consultas válidas para el vector store subyacente.
    *   **Rendimiento y Escalabilidad**: Las búsquedas vectoriales pueden ser costosas. QS debe estar optimizado y ser escalable.
    *   **Manejo de Errores**: Si una colección no se encuentra, el vector store no responde, o ES falla al generar un embedding, QS debe manejar estos errores grácilmente y reportarlos en la respuesta a AES.
    *   **Seguridad**: Asegurar que las búsquedas se realicen dentro del contexto del `tenant_id` y que solo se acceda a las colecciones permitidas.

## 6.2 Comunicaciones Salientes desde QueryService (QS)

La principal comunicación saliente documentada para QS es el callback hacia AES, que podría usarse en escenarios de procesamiento RAG asíncrono.

### Interacción 6.2.1: `Query Service (QS) -> AES: Callback de Generación de Respuesta RAG`

*   Esta interacción ya fue detallada desde la perspectiva de AES como receptor (Ver Interacción 2.2.2). Desde la perspectiva de QS como iniciador:
    *   **Contexto**: Si QS procesara una solicitud de `query.rag.async` (no documentada aún como entrante a QS, pero hipotética dada la existencia del callback en AES) o si un flujo interno en QS necesitara notificar a AES sobre resultados RAG.
    *   **Destino**: `Agent Execution Service`, cola `query:callbacks:{tenant_id}:{session_id}`.
    *   **Payload**: Como se describió en 2.2.2, incluyendo `status`, `results`, `error_message`, `correlation_id` (de la solicitud original a QS), etc.
    *   **Observación**: La documentación de QS debería clarificar cuándo y bajo qué circunstancias QS inicia estos callbacks. Si solo existe `query.rag.sync` como acción principal, el callback podría ser para notificaciones secundarias o un remanente.

### Interacción 6.2.2: `Query Service (QS) -> ES: Generar Embedding para Consulta (Interno)`

*   **Contexto y Justificación Detallada**: Cuando QS recibe una solicitud `query.rag.sync` (Interacción 6.1.1), parte de su trabajo es convertir el texto de la consulta del usuario en un vector de embedding. Este embedding se utiliza luego para buscar documentos similares en el vector store. QS delega la tarea de generación de embeddings al Embedding Service (ES). Esta es una comunicación interna crítica para el funcionamiento de QS.
*   **Iniciador (Cliente)**: `Query Service`, probablemente desde su `query_service.handlers.query_handler.QueryHandler` o una lógica de servicio interna cuando procesa `query.rag.sync`.
*   **Destino (Servidor)**: `Embedding Service`, procesado por `embedding_service.workers.embedding_worker.EmbeddingWorker` (acción `embedding.generate.sync`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues (QS espera la respuesta de ES antes de proceder con la búsqueda vectorial).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `embedding.generate.sync` (QS actúa como cliente de ES, usando la misma acción que AES usaría).
    *   Cola de Solicitud (Enviada por QS): `embedding.actions`.
    *   Patrón de Cola de Respuesta (Esperada por QS): `embedding:responses:generate:{correlation_id_qs_es}` (QS genera un nuevo `correlation_id` para esta sub-solicitud a ES).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Enviado por QS a ES)**:
        ```json
        {
          "action_id": "<uuid4_accion_qs_a_es>",
          "action_type": "embedding.generate.sync",
          "tenant_id": "<id_del_tenant_original_de_aes>",
          "correlation_id": "<uuid_correlacion_generado_por_qs_para_esta_llamada_a_es>",
          "timestamp": "<iso_timestamp_qs>",
          "data": {
            "texts": ["¿Cuál es la política de devoluciones?"], // El texto de la consulta original de AES
            "model": "openai/text-embedding-ada-002", // El modelo específico para la colección actual que QS está procesando
            // "collection_id": "<uuid_collection_actual>", // Opcional, para contexto en ES
            // "session_id": "<id_sesion_original_de_aes>", // Opcional, para contexto en ES
            "tenant_id": "<id_del_tenant_original_de_aes>",
            "correlation_id": "<mismo_uuid_correlacion_generado_por_qs>"
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud QS->ES)*:
          *   `data.texts`: Contiene un array con un solo elemento: el texto de la consulta del usuario que QS necesita embeber.
          *   `data.model`: Este es el `embedding_model` que AES especificó para la `collection_id` particular que QS está procesando en ese momento. QS debe realizar esta llamada a ES por cada colección con un modelo de embedding diferente.

    *   **Payload de Respuesta (Esperado por QS de ES)**:
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_correlacion_generado_por_qs>",
          "data": {
            "embeddings": [
              [0.00123, -0.00456, ..., 0.00789] // Embedding para la consulta
            ],
            "model_used": "openai/text-embedding-ada-002",
            "usage": { "prompt_tokens": 10, "total_tokens": 10 }
          },
          "error": null
        }
        ```
        *Consideraciones para QS al Recibir la Respuesta de ES*:
          *   QS extrae el vector de `data.embeddings[0]`.
          *   Utiliza este vector para realizar la búsqueda en el vector store de la colección actual.
          *   Si `success` es `false` o hay un `error`, QS debe manejarlo: podría intentar un reintento, fallar la búsqueda para esa colección específica, o fallar toda la solicitud RAG de AES.

*   **Estado de Implementación**: Lógica implícita existente en QS para llamar a ES. Esta documentación la hace explícita.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Dependencia Crítica**: Esta interacción es fundamental. Si ES falla o es lento, el rendimiento de QS se ve directamente afectado.
    *   **Múltiples Llamadas**: Si una solicitud RAG de AES a QS incluye múltiples colecciones con diferentes modelos de embedding, QS realizará múltiples llamadas secuenciales (o potencialmente paralelas si está optimizado) a ES, una por cada modelo de embedding distinto.
    *   **Gestión de `correlation_id`**: QS actúa como cliente aquí. Genera su propio `correlation_id` para la llamada a ES y lo usa para esperar la respuesta. Este `correlation_id` es diferente del `correlation_id` de la solicitud original de AES a QS.
    *   **Error Handling**: QS debe tener una estrategia robusta para manejar fallos de ES (ej. reintentos, timeouts, circuit breakers).
    *   **Consistencia del Modelo**: QS es responsable de pasar el `embedding_model` correcto (obtenido de la solicitud de AES) a ES para cada consulta de colección.

# 7. Ingestion Service (IS)

El Ingestion Service (IS) se encarga de procesar fuentes de datos (archivos, URLs, texto plano), dividirlas en fragmentos (chunks) manejables, y coordinar la generación de embeddings para estos fragmentos antes de que puedan ser almacenados en una base de datos vectorial para su uso en RAG.

## 7.1 Comunicaciones Entrantes a IngestionService (IS)

Esta sección describe las interacciones que IS recibe para iniciar y gestionar los procesos de ingestión.

### Interacción 7.1.1: `Agent Management Service (AMS) -> IS: Iniciar Ingestión de Documentos para Colección`

*   **Contexto y Justificación Detallada**: Cuando se crea o actualiza una colección en AMS y se le asocian documentos (o se actualizan los existentes), AMS necesita instruir a IS para que procese estos documentos. IS tomará los documentos, los dividirá en chunks y luego solicitará embeddings para esos chunks.
*   **Iniciador (Cliente)**: `Agent Management Service`, probablemente desde un worker o handler que procesa la creación/actualización de colecciones y sus documentos asociados.
*   **Destino (Servidor)**: `Ingestion Service`, procesado por `ingestion_service.workers.ingestion_worker.IngestionWorker`.
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues (AMS envía la acción y no espera una respuesta directa inmediata, aunque IS podría enviar notificaciones de estado/finalización más tarde a AMS u otro servicio).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `ingestion.process_collection_documents` (o un nombre similar, como se definió en la Interacción 3.2.1).
    *   Cola de Solicitud (Escuchada por IS): `ingestion.actions`.
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Recibido por IS de AMS)** (Corresponde a la Interacción 3.2.1):
        ```json
        {
          "action_id": "<uuid4_accion_ams_a_is>",
          "action_type": "ingestion.process_collection_documents",
          "tenant_id": "<id_del_tenant>",
          "correlation_id": "<uuid_opcional_para_seguimiento_ams>", // AMS podría usarlo para rastrear el inicio
          "timestamp": "<iso_timestamp_ams>",
          "data": {
            "collection_id": "<uuid_de_la_coleccion>",
            "embedding_model": "openai/text-embedding-ada-002", // CRÍTICO: IS usará este modelo al solicitar embeddings a ES para los chunks
            "documents": [
              {
                "document_id": "<uuid_documento_1>",
                "source_type": "file_upload", // "url", "text_input"
                "source_uri": "tenant_uploads/<tenant_id>/<filename_original>.pdf", // O URL, o identificador para texto
                "metadata": { "filename": "doc1.pdf", "category": "manuals" }, // Metadatos originales
                "processing_options": { // Opcional, específico del documento
                  "chunking_strategy": "semantic", // "fixed_size", etc.
                  "max_chunk_size": 512
                }
              },
              {
                "document_id": "<uuid_documento_2>",
                "source_type": "url",
                "source_uri": "https://example.com/knowledge_base/article1",
                "metadata": { "title": "Article 1" }
              }
            ],
            "force_reingest": false, // Si es true, IS debe re-procesar incluso si ya lo hizo
            "priority": 10 // Opcional, para priorizar trabajos de ingestión
          }
        }
        ```
        *Consideraciones para IS al Procesar la Solicitud*:
          *   IS debe iterar sobre cada documento en `data.documents`.
          *   Para cada documento, IS necesita: 
              1.  Obtener el contenido (descargar archivo, scrapear URL, etc.).
              2.  Dividir el contenido en chunks según la estrategia definida (global o por documento).
              3.  Para cada chunk, IS deberá luego solicitar su embedding al Embedding Service (ES) usando el `data.embedding_model` (Ver Interacción 7.2.1).
          *   `collection_id` es crucial para asociar los chunks procesados y sus embeddings a la colección correcta.
          *   `embedding_model` es vital, ya que todos los chunks de esta colección deben usar este modelo.
          *   IS debe manejar diferentes `source_type` apropiadamente.
          *   Debe considerar `force_reingest` para decidir si procesar documentos ya conocidos.
          *   IS podría enviar actualizaciones de progreso (posiblemente vía WebSockets o a otra cola Redis, no detallado aquí como comunicación directa AMS-IS).

*   **Estado de Implementación**: Asumido como implementado en IS (worker/handler) y en AMS para enviar la acción.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva IS)**:
    *   **Procesamiento Intensivo**: La ingestión puede ser un proceso largo y que consume muchos recursos (descarga, parseo, chunking).
    *   **Dependencia de ES**: IS depende críticamente de ES para obtener los embeddings de los chunks.
    *   **Manejo de Errores**: IS debe ser robusto frente a errores de descarga, parseo de formatos de archivo, fallos de ES, etc. Debe tener mecanismos de reintento y reporte de fallos (posiblemente a AMS, ver Interacción 7.2.2).
    *   **Chunking Strategies**: La lógica de chunking es compleja y crucial para la calidad del RAG. IS encapsula esta complejidad.
    *   **Idempotencia**: Si `force_reingest` es `false`, IS debería evitar re-procesar documentos/chunks idénticos si ya existen y están actualizados.
    *   **Seguridad y Acceso a Datos**: IS debe operar dentro del contexto del `tenant_id` y manejar de forma segura el acceso a las fuentes de datos.
    *   **Escalabilidad**: IS debe ser capaz de manejar múltiples trabajos de ingestión en paralelo.

## 7.2 Comunicaciones Salientes desde IngestionService (IS)

Una vez que IS ha procesado los documentos en chunks, necesita obtener embeddings para ellos y luego almacenarlos. También puede necesitar notificar el estado del proceso.

### Interacción 7.2.1: `Ingestion Service (IS) -> ES: Generar Embeddings para Chunks de Documentos`

*   **Contexto y Justificación Detallada**: Después de que IS ha descargado, parseado y dividido un documento en múltiples fragmentos (chunks), cada chunk necesita ser convertido en un vector de embedding para la búsqueda semántica. IS delega esta tarea al Embedding Service (ES).
*   **Iniciador (Cliente)**: `Ingestion Service`, desde su `ingestion_service.workers.ingestion_worker.IngestionWorker` después de que los chunks han sido preparados.
*   **Destino (Servidor)**: `Embedding Service`, procesado por `embedding_service.workers.embedding_worker.EmbeddingWorker` (acción `embedding.generate.sync`).
*   **Patrón de Comunicación**: Pseudo-Síncrono vía Redis Queues. IS probablemente envía lotes de chunks a ES y espera la respuesta para ese lote antes de proceder (por ejemplo, antes de almacenar los chunks y sus embeddings en el vector store).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `embedding.generate.sync` (IS actúa como cliente de ES).
    *   Cola de Solicitud (Enviada por IS): `embedding.actions`.
    *   Patrón de Cola de Respuesta (Esperada por IS): `embedding:responses:generate:{correlation_id_is_es}` (IS genera un `correlation_id` para esta solicitud a ES).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Enviado por IS a ES)**:
        ```json
        {
          "action_id": "<uuid4_accion_is_a_es>",
          "action_type": "embedding.generate.sync",
          "tenant_id": "<id_del_tenant_original_de_ams>",
          "correlation_id": "<uuid_correlacion_generado_por_is_para_esta_llamada_a_es>",
          "timestamp": "<iso_timestamp_is>",
          "data": {
            "texts": [
              "Texto del chunk 1 del documento X...",
              "Texto del chunk 2 del documento X...",
              // ... hasta un límite de lote razonable para ES
              "Texto del chunk N del documento X..."
            ],
            "model": "openai/text-embedding-ada-002", // El modelo especificado por AMS para la colección
            "collection_id": "<uuid_de_la_coleccion_original_de_ams>", // Para contexto/logging en ES
            "document_id": "<uuid_documento_original_de_ams>", // Para contexto/logging en ES
            "tenant_id": "<id_del_tenant_original_de_ams>",
            "correlation_id": "<mismo_uuid_correlacion_generado_por_is>"
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud IS->ES)*:
          *   `data.texts`: Un array de strings, donde cada string es el contenido de un chunk.
          *   `data.model`: El `embedding_model` que AMS especificó para la `collection_id` a la que pertenecen estos chunks.

    *   **Payload de Respuesta (Esperado por IS de ES)**:
        ```json
        {
          "success": true,
          "correlation_id": "<mismo_uuid_correlacion_generado_por_is>",
          "data": {
            "embeddings": [
              [0.001, -0.002, ...], // Embedding para chunk 1
              [0.003, -0.004, ...], // Embedding para chunk 2
              // ...
              [0.005, -0.006, ...]  // Embedding para chunk N
            ],
            "model_used": "openai/text-embedding-ada-002",
            "usage": { "prompt_tokens": 1500, "total_tokens": 1500 }
          },
          "error": null
        }
        ```
        *Consideraciones para IS al Recibir la Respuesta de ES*:
          *   IS debe asociar cada embedding recibido con su chunk original (basado en el orden).
          *   Si `success` es `false` o hay un `error`, IS debe manejarlo (reintentar el lote, marcar chunks como fallidos, notificar error general de ingestión).
          *   Una vez que los embeddings se obtienen, IS procede a almacenar los chunks y sus embeddings en el vector store correspondiente a la `collection_id`.

*   **Estado de Implementación**: Lógica implícita existente en IS para llamar a ES. Esta documentación la hace explícita.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Procesamiento por Lotes**: Es crucial que IS envíe chunks a ES en lotes para eficiencia, en lugar de uno por uno. El tamaño del lote debe ser configurable y considerar los límites de ES.
    *   **Dependencia Crítica**: Similar a QS, la funcionalidad de IS depende directamente de la disponibilidad y rendimiento de ES.
    *   **Manejo de `correlation_id`**: IS genera su propio `correlation_id` para cada lote enviado a ES.
    *   **Error Handling a Nivel de Lote/Chunk**: IS necesita una estrategia para manejar fallos parciales (algunos chunks en un lote fallan en ES) o totales.
    *   **Paso Siguiente: Almacenamiento en Vector Store**: Después de obtener los embeddings, el siguiente paso (no basado en colas Redis) es que IS escriba los chunks y sus embeddings en la base de datos vectorial. Esta interacción es directa con el datastore (e.g., Weaviate, Pinecone) y no se detalla aquí como comunicación inter-servicio vía Redis.

### Interacción 7.2.2: `Ingestion Service (IS) -> AMS: Notificar Estado/Finalización de Ingestión`

*   **Contexto y Justificación Detallada**: Una vez que IS ha completado (o fallado) el procesamiento de los documentos para una colección solicitada por AMS (Interacción 7.1.1), debe notificar a AMS sobre el resultado. Esto permite a AMS actualizar el estado de la colección (e.g., marcarla como 'lista para RAG', 'ingestión fallida', 'parcialmente ingerida') y potencialmente informar al usuario.
*   **Iniciador (Cliente)**: `Ingestion Service`, desde su `ingestion_service.workers.ingestion_worker.IngestionWorker` al finalizar un trabajo de ingestión.
*   **Destino (Servidor)**: `Agent Management Service`, procesado por un worker/handler en AMS que escucha estas notificaciones (e.g., `agent_management_service.workers.management_worker.ManagementWorker`).
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `ingestion.status_update` o `ingestion.completion_notification` (o un nombre similar).
    *   Cola de Solicitud (Enviada por IS): `ams.notifications` o una cola específica como `ams.ingestion_callbacks`.
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Notificación (Enviado por IS a AMS)**:
        ```json
        {
          "action_id": "<uuid4_accion_is_a_ams_notificacion>",
          "action_type": "ingestion.status_update",
          "tenant_id": "<id_del_tenant>",
          "correlation_id": "<uuid_correlacion_original_de_ams_a_is>", // Opcional, si AMS lo envió y IS lo guardó
          "timestamp": "<iso_timestamp_is_notificacion>",
          "data": {
            "collection_id": "<uuid_de_la_coleccion_procesada>",
            "status": "completed", // "failed", "completed_with_errors", "in_progress"
            "summary": {
              "total_documents_requested": 5,
              "documents_processed_successfully": 4,
              "documents_failed": 1,
              "total_chunks_created": 250,
              "chunks_embedded_successfully": 245,
              "start_time": "<iso_timestamp_inicio_ingestion>",
              "end_time": "<iso_timestamp_fin_ingestion>"
            },
            "errors": [
              {
                "document_id": "<uuid_documento_fallido>",
                "error_message": "No se pudo descargar el archivo desde la URL.",
                "error_code": "DOWNLOAD_FAILED"
              }
              // ... más errores si los hubo
            ],
            "details_url": "/ingestion_logs/<job_id>" // Opcional, enlace a logs más detallados si existe
          }
        }
        ```
        *Explicación de Campos Clave (Notificación IS->AMS)*:
          *   `data.collection_id`: Identifica la colección cuyo estado se está actualizando.
          *   `data.status`: Estado general del proceso de ingestión para esta colección.
          *   `data.summary`: Estadísticas clave sobre el proceso.
          *   `data.errors`: Lista de errores detallados si `status` no es 'completed'.
          *   `correlation_id`: Podría ser el `correlation_id` que AMS envió en la solicitud original a IS, permitiendo a AMS correlacionar esta notificación con su solicitud inicial.

*   **Estado de Implementación**: Hipotético/Recomendado. Es una parte lógica del flujo de ingestión, pero su implementación específica (nombre de acción, cola) necesita ser confirmada o definida.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Cierre del Ciclo**: Esta notificación cierra el ciclo de la solicitud de ingestión iniciada por AMS.
    *   **Actualización de Estado en AMS**: AMS usaría esta información para actualizar sus propios registros sobre el estado de la colección.
    *   **Visibilidad para el Usuario**: A través de AMS, esta información podría hacerse visible para el usuario final (e.g., en una UI de gestión de colecciones).
    *   **Granularidad de la Notificación**: Podría haber notificaciones intermedias (`status: "in_progress"` con `percentage_complete`) o solo una notificación final.
    *   **Manejo de Fallos en AMS**: AMS debe estar preparado para manejar notificaciones de `status: "failed"` y tomar acciones apropiadas (e.g., marcar la colección como no usable, notificar al administrador).
    *   **Cola de Notificaciones**: Es importante definir una cola clara para estas notificaciones para que AMS pueda escucharlas eficientemente.

# 8. Agent Orchestrator Service (AOS)

El Agent Orchestrator Service (AOS) actúa como una pasarela entre los clientes frontend (conectados vía WebSockets) y el Agent Execution Service (AES). Su función principal es gestionar las conexiones WebSocket, recibir mensajes de los usuarios, enviarlos a AES para su procesamiento por el agente correspondiente, y luego retransmitir las respuestas del agente de vuelta al cliente correcto a través del WebSocket.

## 8.1 Comunicaciones Salientes desde Agent Orchestrator Service (AOS)

Cuando un usuario envía un mensaje a través de una conexión WebSocket, AOS lo procesa y lo reenvía a AES.

### Interacción 8.1.1: `AOS -> AES: Enviar Mensaje de Usuario / Ejecutar Agente`

*   **Contexto y Justificación Detallada**: Un usuario conectado vía WebSocket envía un mensaje destinado a un agente. AOS recibe este mensaje y debe pasarlo a AES para que el agente lo procese y genere una respuesta. Esta es la vía principal para la interacción del usuario con los agentes.
*   **Iniciador (Cliente)**: `Agent Orchestrator Service`, tras recibir un mensaje de un cliente WebSocket.
*   **Destino (Servidor)**: `Agent Execution Service`, específicamente la cola escuchada por `agent_execution_service.workers.execution_worker.ExecutionWorker`.
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues. AOS envía la acción y no espera una respuesta directa en esta misma transacción. Esperará una respuesta de AES a través de una cola de callbacks o un patrón de respuesta dedicado (ver Interacción 8.2.1).
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `execution.agent_run` (o un tipo de acción similar que AES espera para iniciar la ejecución de un agente).
    *   Cola de Solicitud (Enviada por AOS): `agent_execution_service:actions` (o la cola principal de acciones de AES).
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Solicitud (Enviado por AOS a AES)**:
        ```json
        {
          "action_id": "<uuid4_accion_aos_a_aes>",
          "action_type": "execution.agent_run",
          "tenant_id": "<id_del_tenant_asociado_al_usuario_o_websocket>",
          "correlation_id": "<uuid_correlacion_aos_para_rastrear_respuesta_aes>", // Crucial para mapear la respuesta de AES al WebSocket correcto
          "timestamp": "<iso_timestamp_aos>",
          "data": {
            "agent_id": "<uuid_del_agente_objetivo>",
            "session_id": "<id_de_sesion_websocket_o_conversacion>", // Identificador único de la conversación/sesión del usuario
            "user_input": "Hola agente, ¿cómo estás?",
            "message_id": "<uuid_mensaje_del_cliente_frontend>", // Opcional, ID del mensaje original del cliente
            "metadata": { // Metadatos adicionales del cliente o de la sesión
              "user_agent": "WebApp v1.2",
              "preferred_language": "es-ES"
            },
            "response_channel_hint": "aos:callbacks:{websocket_connection_id}" // SUGERENCIA: AOS podría indicar a AES dónde enviar la respuesta específica para esta interacción
          }
        }
        ```
        *Explicación de Campos Clave (Solicitud AOS->AES)*:
          *   `tenant_id`: Necesario para que AES aplique la lógica de negocio y seguridad correcta.
          *   `correlation_id`: Generado por AOS. AES deberá incluir este ID en su respuesta para que AOS pueda enrutarla al cliente WebSocket correcto.
          *   `data.agent_id`: Identifica el agente que debe procesar el mensaje.
          *   `data.session_id`: Mantiene el contexto de la conversación.
          *   `data.user_input`: El mensaje del usuario.
          *   `data.response_channel_hint`: Aunque AES podría tener una cola de callback genérica para AOS, una sugerencia más específica podría ayudar a enrutar respuestas si AOS maneja muchas conexiones. Alternativamente, AES podría responder a una cola general y AOS usaría el `correlation_id` para el enrutamiento.

*   **Estado de Implementación**: Asumido como implementado en AOS para enviar y en AES para recibir y procesar `execution.agent_run`.
*   **Análisis Crítico y Observaciones Clave**:
    *   **Mapeo WebSocket a `correlation_id`**: AOS debe mantener un mapeo entre las conexiones WebSocket activas y los `correlation_id` que envía a AES. Cuando AES responda (ver 8.2.1), AOS usará este `correlation_id` para encontrar el WebSocket del cliente y reenviar la respuesta.
    *   **Gestión de Sesiones**: `session_id` es vital para que AES y los servicios subsiguientes (como CS) mantengan el contexto de la conversación.
    *   **Seguridad**: AOS debe validar la autenticación/autorización del usuario antes de enviar la acción a AES. El `tenant_id` debe ser confiable.
    *   **Escalabilidad de AOS**: AOS debe ser capaz de manejar un gran número de conexiones WebSocket concurrentes.
    *   **Manejo de Errores de AES**: Si AES no puede procesar la solicitud (e.g., agente no encontrado, error interno de AES), AES debería idealmente enviar una respuesta de error a AOS (vía el mecanismo de respuesta) para que AOS pueda informar al cliente.

## 8.2 Comunicaciones Entrantes a Agent Orchestrator Service (AOS)

AES necesita una forma de devolver las respuestas del agente (o errores) a AOS para que puedan ser transmitidas al cliente WebSocket correcto.

### Interacción 8.2.1: `AES -> AOS: Respuesta del Agente / Callback`

*   **Contexto y Justificación Detallada**: Después de que AES procesa una acción `execution.agent_run` (iniciada por AOS en 8.1.1), genera una respuesta (o un error). Esta respuesta debe ser devuelta a AOS, que luego la reenviará al cliente WebSocket original que espera la contestación del agente.
*   **Iniciador (Cliente)**: `Agent Execution Service`, desde su `agent_execution_service.workers.execution_worker.ExecutionWorker` (o un handler/componente que este invoque para enviar respuestas).
*   **Destino (Servidor)**: `Agent Orchestrator Service`. AOS debe tener un worker o un mecanismo que escuche en una cola de respuestas/callbacks específica.
*   **Patrón de Comunicación**: Asíncrono vía Redis Queues.
*   **Detalles de la Acción y Colas**:
    *   `action_type`: `execution.agent_response` o `agent.callback.result` (o un nombre similar que AOS espere).
    *   Cola de Solicitud (Enviada por AES, Escuchada por AOS): `aos.callbacks` o `aos:responses:{correlation_id}` o `aos:responses:{websocket_connection_id}` (si se usó el `response_channel_hint` de 8.1.1). Una cola general `aos.callbacks` es más probable, donde AOS usa el `correlation_id` para el enrutamiento interno.
*   **Esquemas de Payload y Ejemplos Detallados**:
    *   **Payload de Respuesta/Callback (Recibido por AOS de AES)**:
        ```json
        {
          "action_id": "<uuid4_accion_aes_a_aos_respuesta>",
          "action_type": "execution.agent_response",
          "tenant_id": "<id_del_tenant_original>",
          "correlation_id": "<uuid_correlacion_original_de_aos_a_aes>", // CRÍTICO: AOS usa esto para encontrar el WebSocket
          "timestamp": "<iso_timestamp_aes_respuesta>",
          "data": {
            "session_id": "<id_de_sesion_original>",
            "agent_response": {
              "type": "text", // "image", "options", "error"
              "content": "Aquí está la respuesta del agente.",
              "ui_elements": [/* Opcional: para renderizar elementos ricos en el frontend */],
              "source_documents": [/* Opcional: documentos usados en RAG */]
            },
            "status": "success", // "error"
            "error_details": null, // O un objeto de error si status es "error"
            // "original_message_id": "<uuid_mensaje_original_del_cliente>" // Opcional, si AOS lo envió
          }
        }
        ```
        *Explicación de Campos Clave (Respuesta AES->AOS)*:
          *   `correlation_id`: Esencial. AOS lo usa para buscar la conexión WebSocket del cliente que originó la solicitud y enviar esta respuesta a ese cliente.
          *   `data.agent_response.type`: Indica cómo el frontend debe renderizar la respuesta.
          *   `data.agent_response.content`: El contenido principal de la respuesta.
          *   `data.status` y `data.error_details`: Para comunicar el éxito o fallo de la ejecución del agente.

*   **Estado de Implementación**: Asumido como implementado en AES para enviar y en AOS para recibir y procesar estas respuestas/callbacks.
*   **Análisis Crítico y Observaciones Clave (desde perspectiva AOS)**:
    *   **Enrutamiento por `correlation_id`**: La función más crítica de AOS al recibir este mensaje es usar el `correlation_id` para identificar la conexión WebSocket correcta y reenviar `data.agent_response` (o un mensaje de error) a ese cliente.
    *   **Manejo de Múltiples Tipos de Respuesta**: AOS debe ser capaz de manejar diferentes `data.agent_response.type` y formatearlos adecuadamente para el protocolo WebSocket si es necesario (aunque usualmente se envía el JSON tal cual).
    *   **Manejo de Errores desde AES**: Si `data.status` es `"error"`, AOS debe transmitir esta condición de error al cliente WebSocket.
    *   **Timeouts y Conexiones Perdidas**: AOS debe manejar escenarios donde el cliente WebSocket se desconecta antes de que llegue la respuesta de AES. El mapeo de `correlation_id` a WebSocket debe manejar estas situaciones (e.g., no intentar enviar si el socket ya no existe).
    *   **Seguridad de la Cola de Callback**: Asegurar que solo AES (u otros servicios autorizados) puedan publicar en la cola de callbacks de AOS.

