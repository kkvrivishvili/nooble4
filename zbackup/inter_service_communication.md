# Documento de Comunicación Inter-Servicios en Nooble4

## Objetivo

Este documento tiene como objetivo detallar los patrones de comunicación, las colas Redis utilizadas, los payloads intercambiados, y las responsabilidades de cada servicio dentro del ecosistema Nooble4 en lo que respecta a la comunicación basada en mensajes. Se centra principalmente en las interacciones que utilizan Redis como bus de mensajes para la ejecución de `DomainActions` y el intercambio de datos de forma pseudo-síncrona y asíncrona.

Este documento se irá actualizando a medida que se revisen los componentes de cada servicio para reflejar el estado actual de la implementación, identificando también áreas de mejora o información incompleta en los payloads.

## Estructura del Documento por Servicio

Para cada servicio, se analizarán sus interacciones salientes (cuando actúa como cliente de otro servicio) y sus interacciones entrantes (cuando actúa como servidor procesando solicitudes de otros).

Para cada interacción específica (ej. AES llamando a Agent Management Service para obtener configuración), se detallará:

*   **Flujo**: Descripción general de la interacción (ej. `AES -> Agent Management Service: Obtener Configuración de Agente`).
*   **Servicio Emisor (Cliente)**: Quién inicia la solicitud.
*   **Componente Emisor**: Clase/módulo específico en el servicio emisor (ej. `AgentExecutionService/clients/agent_management_client.py`).
*   **Acción Solicitada (`action_type`)**: El `action_type` del `DomainAction` enviado (ej. `management.get_agent_config`).
*   **Cola de Solicitud Redis**: Nombre de la cola a la que se publica la solicitud (ej. `management.actions`).
*   **Payload de Solicitud (Detalle)**:
    ```json
    // Estructura JSON del payload enviado
    ```
*   **Servicio Receptor (Servidor)**: Quién procesa la solicitud.
*   **Componente Receptor**: Clase/módulo específico en el servicio receptor (ej. `AgentManagementService/workers/management_worker.py` y `AgentManagementService/handlers/agent_handler.py`).
*   **Cola de Respuesta Redis (Patrón)**: Cómo se construye el nombre de la cola donde el cliente espera la respuesta (ej. `management:responses:get_agent_config:<correlation_id>`).
*   **Payload de Respuesta (Detalle)**:
    ```json
    // Estructura JSON del payload de respuesta
    ```
*   **Estado y Observaciones**: 
    *   ¿Está completamente implementado?
    *   ¿El payload es completo y útil?
    *   Sugerencias de mejora o campos faltantes/adicionales.

---

## Servicios

### 1. Agent Execution Service (AES)

#### 1.1. Interacciones Salientes (AES como Cliente)

##### 1.1.1. AES -> Agent Management Service (AMS): Obtener Configuración de Agente

*   **Flujo**: AES necesita la configuración detallada de un agente para poder ejecutarlo. Solicita esta información al AMS.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/agent_management_client.py` (Clase `AgentManagementClient`, método `get_agent_config`)
*   **Acción Solicitada (`action_type`)**: `management.get_agent_config`
*   **Cola de Solicitud Redis**: `management.actions`
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "management.get_agent_config",
      "task_id": null, // No se establece explícitamente en el cliente
      "tenant_id": null, // No se establece explícitamente en el cliente para el DomainAction general, va en data
      "tenant_tier": null, // No se establece explícitamente
      "timestamp": "<iso_timestamp>", // Autogenerado
      "data": {
        "agent_id": "string (UUID format)",
        "tenant_id": "string",
        "correlation_id": "string (UUID format, generado por el cliente para la respuesta)"
      }
    }
    ```
*   **Servicio Receptor (Servidor)**: Agent Management Service (AMS)
*   **Componente Receptor (Asumido)**: `AgentManagementService/workers/management_worker.py` y un handler específico (ej. `AgentManagementService/handlers/agent_handler.py`). *(Pendiente de confirmación al revisar AMS)*.
*   **Cola de Respuesta Redis (Patrón)**: `management:responses:get_agent_config:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola).
*   **Payload de Respuesta (Esperado por el cliente AES)**:
    ```json
    {
      "success": true, // o false
      "agent_config": {
        // Detalles de la configuración del agente
        // Según el TODO en el cliente, esto debería incluir:
        // - system_prompt: "string",
        // - model_name: "string",
        // - temperature: float,
        // - max_tokens: int,
        // - tools: [],
        // - collections: [
        //   { "collection_id": "uuid", "embedding_model": "string" },
        //   ...
        // ],
        // - ... (otras configuraciones relevantes)
      },
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   La comunicación pseudo-síncrona está implementada usando `correlation_id` y `BLPOP`.
    *   **CRÍTICO**: El payload de `agent_config` devuelto por AMS necesita ser exhaustivo. Actualmente, el cliente AES tiene un `TODO` (líneas 77-85 en `agent_management_client.py`) que especifica la información detallada que se espera:
        *   Configuración básica del agente (system prompt, modelo, configuraciones de LLM).
        *   Lista de `collection_id`s asociadas para RAG.
        *   Modelos de embeddings asignados a cada `collection_id`.
        *   Cualquier otra configuración relevante para la ejecución del agente (ej. herramientas habilitadas, límites, etc.).
    *   La idea es que AMS sea la fuente de verdad para toda la configuración estática del agente, evitando que AES tenga que consultar otros servicios (como Ingestion Service) para obtener metadatos de collections.
    *   El `DomainAction` enviado por el cliente no establece `task_id`, `tenant_id` (a nivel raíz, sí en `data`), ni `tenant_tier` explícitamente. Estos podrían ser heredados o establecidos por el `DomainQueueManager` o ser opcionales para este tipo de acción interna.

---

##### 1.1.2. AES -> Conversation Service (CS): Obtener Historial de Conversación

*   **Flujo**: AES necesita el historial de una conversación para proporcionar contexto al agente. Solicita este historial al CS.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/conversation_client.py` (Clase `ConversationServiceClient`, método `get_conversation_history`)
*   **Acción Solicitada (`action_type`)**: `conversation.get_history`
*   **Cola de Solicitud Redis**: `conversation.actions` (El método `enqueue_action` del `DomainQueueManager` probablemente construye el nombre completo de la cola a partir del prefijo "conversation").
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "conversation.get_history",
      "task_id": null, // No se establece explícitamente en el cliente
      "tenant_id": "string (valor del argumento tenant_id)",
      "session_id": "string (valor del argumento session_id)", // También usado a nivel raíz del DomainAction
      "timestamp": "<iso_timestamp>", // Autogenerado
      "correlation_id": "string (UUID, generado por el cliente, mismo que en data.correlation_id)", // Usado a nivel raíz del DomainAction
      "data": {
        "limit": "integer",
        "include_system": "boolean",
        "correlation_id": "string (UUID, generado por el cliente para la respuesta)"
      }
    }
    ```
*   **Servicio Receptor (Servidor)**: Conversation Service (CS)
*   **Componente Receptor (Asumido)**: `ConversationService/workers/conversation_worker.py` y un handler específico (ej. `ConversationService/handlers/history_handler.py`). *(Pendiente de confirmación al revisar CS)*.
*   **Cola de Respuesta Redis (Patrón)**: `conversation:responses:get_history:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola a través del método `_wait_for_response`).
*   **Payload de Respuesta (Esperado por el cliente AES)**:
    ```json
    {
      "success": true, // o false
      "correlation_id": "string (UUID, debe coincidir con el de la solicitud)",
      "data": {
        "messages": [
          // Lista de objetos de mensaje. Ejemplo:
          // { "role": "user", "content": "Hola", "timestamp": "...", ... },
          // { "role": "assistant", "content": "¿Cómo puedo ayudarte?", ... }
        ]
      },
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   La comunicación pseudo-síncrona está implementada usando `correlation_id` y `BLPOP` (manejado por el método helper `_wait_for_response`).
    *   El `DomainAction` enviado por el cliente establece `tenant_id`, `session_id`, y `correlation_id` a nivel raíz. El `correlation_id` también se incluye dentro del objeto `data`.
    *   El cliente espera una lista de mensajes bajo `response.data.messages`.
    *   El payload de respuesta debería idealmente incluir metadatos adicionales por mensaje si fueran relevantes (ej. `message_id`, `timestamp`, `metadata` específica del mensaje).

---

##### 1.1.3. AES -> Conversation Service (CS): Guardar Mensaje

*   **Flujo**: Después de que un agente genera una respuesta, o para registrar la entrada del usuario, AES guarda el mensaje en el historial de la conversación a través del CS.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/conversation_client.py` (Clase `ConversationServiceClient`, método `save_message`)
*   **Acción Solicitada (`action_type`)**: `conversation.save_message`
*   **Cola de Solicitud Redis**: `conversation.actions` (El método `enqueue_action` del `DomainQueueManager` probablemente construye el nombre completo de la cola a partir del prefijo "conversation").
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "conversation.save_message",
      "task_id": null, // No se establece explícitamente en el cliente
      "tenant_id": "string (valor del argumento tenant_id)",
      "session_id": "string (valor del argumento session_id)", // También usado a nivel raíz del DomainAction
      "timestamp": "<iso_timestamp>", // Autogenerado
      "correlation_id": "string (UUID, generado por el cliente, mismo que en data.correlation_id)", // Usado a nivel raíz del DomainAction
      "data": {
        "role": "string (user/assistant/system)",
        "content": "string",
        "message_type": "string (default 'text')",
        "metadata": "object (default {}, puede contener datos adicionales como tool_calls, sources, etc.)",
        "processing_time": "float (opcional, tiempo que tardó en generarse el mensaje)",
        "correlation_id": "string (UUID, generado por el cliente para la respuesta, si se espera)"
      }
    }
    ```
*   **Servicio Receptor (Servidor)**: Conversation Service (CS)
*   **Componente Receptor (Asumido)**: `ConversationService/workers/conversation_worker.py` y un handler específico (ej. `ConversationService/handlers/message_handler.py`). *(Pendiente de confirmación al revisar CS)*.
*   **Cola de Respuesta Redis (Patrón)**: `conversation:responses:save_message:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola si `wait_for_response` es `True`).
*   **Payload de Respuesta (Esperado por el cliente AES si `wait_for_response` es `True`)**:
    ```json
    {
      "success": true, // o false
      "correlation_id": "string (UUID, debe coincidir con el de la solicitud)",
      "data": {
        // Podría incluir el ID del mensaje guardado para referencia.
        // "message_id": "string_uuid_del_mensaje_guardado"
      },
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   La comunicación puede ser síncrona (esperando confirmación, `wait_for_response=True`) o asíncrona (`wait_for_response=False`).
    *   Si es síncrona, utiliza `correlation_id` y `BLPOP` (manejado por `_wait_for_response`).
    *   El `DomainAction` enviado por el cliente establece `tenant_id`, `session_id`, y `correlation_id` a nivel raíz. El `correlation_id` también se incluye dentro del objeto `data`.
    *   **SUGERENCIA**: El payload de respuesta, cuando se espera, debería incluir el `message_id` del mensaje que se acaba de guardar. Esto sería útil para trazabilidad o si se necesita hacer referencia a ese mensaje específico posteriormente.
    *   El campo `metadata` en la solicitud es genérico (`object`). Sería bueno estandarizar los campos comunes que podrían ir aquí, como `tool_calls`, `sources`, `token_usage`, etc., que son relevantes para los mensajes generados por el agente.
    *   El método `notify_session_closed` que existía previamente en este cliente ha sido eliminado.

---

##### 1.1.4. AES -> Embedding Service (ES): Generar Embeddings (Síncrono)

*   **Flujo**: Cuando AES necesita obtener representaciones vectoriales (embeddings) de textos (por ejemplo, para herramientas de búsqueda semántica o para preparar datos para un modelo), lo solicita al Embedding Service.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/embedding_client.py` (Clase `EmbeddingClient`, método `generate_embeddings_sync`)
*   **Acción Solicitada (`action_type`)**: `embedding.generate.sync`
*   **Cola de Solicitud Redis**: `embedding.actions`
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "embedding.generate.sync",
      "task_id": "<uuid>", // Autogenerado por el cliente
      "tenant_id": "string (valor del argumento tenant_id)",
      "session_id": "string (valor del argumento session_id, dentro de data)", // Nota: session_id está en data, no a nivel raíz como en otros clientes.
      "timestamp": "<iso_timestamp>", // Autogenerado por DomainAction
      "correlation_id": null, // No se establece a nivel raíz en este cliente para la solicitud.
      "data": {
        "texts": [
          "string", // Lista de textos para los que se generarán embeddings
          "...
        ],
        "session_id": "string (valor del argumento session_id)",
        "correlation_id": "string (UUID, generado por el cliente para la respuesta)",
        "model": "string (opcional, ej. 'text-embedding-ada-002')",
        "collection_id": "string (UUID, opcional, para asociar con una colección específica)",
        "metadata": "object (opcional, metadatos adicionales)"
      },
      "context": "object (opcional, si se proporciona ExecutionContext)"
    }
    ```
*   **Servicio Receptor (Servidor)**: Embedding Service (ES)
*   **Componente Receptor (Asumido)**: `EmbeddingService/workers/embedding_worker.py` y un handler para `embedding.generate.sync`. *(Pendiente de confirmación al revisar ES)*.
*   **Cola de Respuesta Redis (Patrón)**: `embedding:responses:generate:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola).
*   **Payload de Respuesta (Esperado por el cliente AES)**:
    ```json
    {
      "success": true, // o false
      // "correlation_id": "string (UUID, debería coincidir con el de la solicitud)", // No se verifica explícitamente en el cliente, pero es el estándar.
      "embeddings": [
        [0.01, 0.02, ..., -0.05], // Vector de embedding para el primer texto
        [...], // Vector para el segundo texto
        // etc.
      ],
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   Utiliza un patrón pseudo-síncrono con `correlation_id` y `BLPOP` en una cola de respuesta específica (`embedding:responses:generate:<correlation_id>`).
    *   A diferencia de otros clientes, el `correlation_id` de la solicitud `DomainAction` a nivel raíz no se establece; solo se usa el `correlation_id` dentro del objeto `data` para nombrar la cola de respuesta y correlacionar.
    *   El `session_id` también se encuentra dentro del objeto `data` en lugar de a nivel raíz del `DomainAction`.
    *   El cliente genera un `task_id` para la acción.
    *   El `action_type` `embedding.generate.sync` indica que es una operación de espera. Podría existir una contraparte asíncrona no usada por este cliente.
    *   Se manejan reintentos (`tenacity`) para la operación completa.
    *   El cliente establece una expiración en la cola de respuesta Redis para evitar colas huérfanas.

---

##### 1.1.5. AES -> Query Service (QS): Generar Respuesta RAG (Síncrono)

*   **Flujo**: Cuando AES necesita obtener una respuesta generada por un modelo de lenguaje aumentada con información de una base de conocimiento (RAG), lo solicita al Query Service.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/query_client.py` (Clase `QueryClient`, método `generate_rag_sync`)
*   **Acción Solicitada (`action_type`)**: `query.rag.sync`
*   **Cola de Solicitud Redis**: `query.actions`
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "query.rag.sync",
      "task_id": "<uuid>", // Autogenerado por el cliente
      "tenant_id": "string (valor del argumento tenant_id)",
      "timestamp": "<iso_timestamp>", // Autogenerado por DomainAction
      "correlation_id": null, // No se establece a nivel raíz.
      "data": {
        "query": "string (la pregunta o consulta del usuario)",
        "session_id": "string (identificador de la sesión de conversación)",
        "collection_ids": [
          "string" // Lista de IDs de las colecciones donde buscar información
        ],
        "correlation_id": "string (UUID, generado por el cliente para la respuesta)",
        "llm_model": "string (opcional, modelo de lenguaje a usar, ej. 'gpt-3.5-turbo')",
        "search_limit": "integer (opcional, default 5, cuántos documentos recuperar)",
        "metadata": "object (opcional, metadatos adicionales para la consulta)"
      },
      "context": "object (opcional, si se proporciona ExecutionContext)"
    }
    ```
*   **Servicio Receptor (Servidor)**: Query Service (QS)
*   **Componente Receptor (Asumido)**: `QueryService/workers/query_worker.py` y un handler para `query.rag.sync`. *(Pendiente de confirmación al revisar QS)*.
*   **Cola de Respuesta Redis (Patrón)**: `query:responses:generate:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola).
*   **Payload de Respuesta (Esperado por el cliente AES)**:
    ```json
    {
      "success": true, // o false
      // "correlation_id": "string (UUID)", // Asumido
      "answer": "string (la respuesta generada por el LLM basada en los documentos)",
      "documents": [
        {
          "id": "string (ID del documento)",
          "content": "string (contenido del fragmento del documento)",
          "score": "float (puntuación de similitud)",
          "metadata": "object (metadatos del documento, ej. fuente, título)"
          // ... otros campos relevantes del documento
        }
      ],
      "metadata": "object (metadatos sobre la generación, ej. tokens usados, tiempo de procesamiento)",
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   Patrón pseudo-síncrono con `correlation_id` (en `data`) y `BLPOP`.
    *   `session_id` está en `data`.
    *   Se genera `task_id`.
    *   El cliente establece expiración en la cola de respuesta y maneja reintentos.

---

##### 1.1.6. AES -> Query Service (QS): Buscar Documentos (Síncrono)

*   **Flujo**: Cuando AES necesita buscar documentos relevantes en una o más colecciones basado en una consulta (sin la parte de generación de lenguaje), lo solicita al Query Service.
*   **Servicio Emisor (Cliente)**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/clients/query_client.py` (Clase `QueryClient`, método `search_documents_sync`)
*   **Acción Solicitada (`action_type`)**: `query.search.sync`
*   **Cola de Solicitud Redis**: `query.actions`
*   **Payload de Solicitud (Detalle)**:
    ```json
    {
      "action_id": "<uuid>", // Autogenerado por DomainAction
      "action_type": "query.search.sync",
      "task_id": "<uuid>", // Autogenerado por el cliente
      "tenant_id": "string (valor del argumento tenant_id)",
      "timestamp": "<iso_timestamp>", // Autogenerado por DomainAction
      "correlation_id": null, // No se establece a nivel raíz.
      "data": {
        "query": "string (la pregunta o consulta del usuario para buscar)",
        "collection_ids": [
          "string" // Lista de IDs de las colecciones donde buscar
        ],
        "correlation_id": "string (UUID, generado por el cliente para la respuesta)",
        "search_limit": "integer (opcional, default 5, cuántos documentos recuperar)"
        // session_id no es parte de esta solicitud específica
      },
      "context": "object (opcional, si se proporciona ExecutionContext)"
    }
    ```
*   **Servicio Receptor (Servidor)**: Query Service (QS)
*   **Componente Receptor (Asumido)**: `QueryService/workers/query_worker.py` y un handler para `query.search.sync`. *(Pendiente de confirmación al revisar QS)*.
*   **Cola de Respuesta Redis (Patrón)**: `query:responses:search:<correlation_id>` (El cliente AES hace `BLPOP` sobre esta cola).
*   **Payload de Respuesta (Esperado por el cliente AES)**:
    ```json
    {
      "success": true, // o false
      // "correlation_id": "string (UUID)", // Asumido
      "documents": [
        {
          "id": "string (ID del documento)",
          "content": "string (contenido del fragmento del documento)",
          "score": "float (puntuación de similitud)",
          "metadata": "object (metadatos del documento, ej. fuente, título)"
          // ... otros campos relevantes del documento
        }
      ],
      "error": "string (mensaje de error si success es false, opcional)"
    }
    ```
*   **Estado y Observaciones**:
    *   Similar a `generate_rag_sync` pero enfocado solo en la recuperación de documentos.
    *   Patrón pseudo-síncrono con `correlation_id` (en `data`) y `BLPOP`.
    *   No incluye `session_id` ni `llm_model` en `data`.
    *   Se genera `task_id`.
    *   El cliente establece expiración en la cola de respuesta y maneja reintentos.

---

### 1.2. Interacciones Originadas por Workers del AES

#### 1.2.1. AES (ExecutionWorker) -> Cola de Callback del Solicitante (Ej: Orchestrator)

*   **Flujo**: Una vez que el `AgentExecutionHandler` completa (o falla) la ejecución de un agente solicitada por una acción `execution.agent_run`, el `ExecutionWorker` envía el resultado (o el error) a la cola de callback que fue especificada en la solicitud original.
*   **Servicio Emisor**: Agent Execution Service (AES)
*   **Componente Emisor**: `agent_execution_service/workers/execution_worker.py` (Clase `ExecutionWorker`, método `_send_callback` que utiliza `agent_execution_service/handlers/execution_callback_handler.py`)
*   **Acción Enviada (`action_type` en el mensaje de callback - Inferido)**: `execution.callback.success` o `execution.callback.error` (El `ExecutionCallbackHandler` lo define).
*   **Cola de Destino Redis**: Dinámica. El valor de `action.callback_queue` de la solicitud `execution.agent_run` original. Ejemplo: `orchestrator:callbacks:<unique_id_o_correlation_id>`.
*   **Payload del Mensaje de Callback (Éxito - Estructura General Inferida)**:
    ```json
    {
      "action_id": "<uuid_nuevo_para_el_callback>",
      "action_type": "execution.callback.success", // Inferido
      "task_id": "string (mismo task_id de la solicitud execution.agent_run original)",
      "tenant_id": "string",
      "session_id": "string",
      "timestamp": "<iso_timestamp>",
      "correlation_id": "<correlation_id_del_callback>", // Podría ser el original o uno nuevo
      "data": {
        // Contenido de result["execution_result"], que puede incluir:
        "output": "string (salida principal del agente, ej. respuesta textual)",
        "tool_calls": [ /* Lista de llamadas a herramientas realizadas */ ],
        "sources": [ /* Lista de fuentes/documentos consultados */ ],
        "token_usage": { /* Información sobre tokens consumidos */ },
        "status": "completed", // u otro estado final
        "execution_time": "float (tiempo total de ejecución)"
        // ... otros campos específicos devueltos por el AgentExecutionHandler
      },
      "context": { // ExecutionContext adjunto al callback
        "tenant_id": "string",
        "tenant_tier": "string",
        "session_id": "string"
      }
    }
    ```
*   **Payload del Mensaje de Callback (Error - Estructura General Inferida)**:
    ```json
    {
      "action_id": "<uuid_nuevo_para_el_callback>",
      "action_type": "execution.callback.error", // Inferido
      "task_id": "string (mismo task_id de la solicitud execution.agent_run original)",
      "tenant_id": "string",
      "session_id": "string",
      "timestamp": "<iso_timestamp>",
      "correlation_id": "<correlation_id_del_callback>",
      "data": {
        "error": {
          "type": "string (ej. 'ValueError', 'AgentTimeoutError')",
          "message": "string (descripción del error)",
          "details": "object (opcional, información adicional del error)"
        },
        "status": "failed",
        "execution_time": "float (opcional, tiempo hasta el fallo)"
      },
      "context": { // ExecutionContext adjunto al callback
        "tenant_id": "string",
        "tenant_tier": "string",
        "session_id": "string"
      }
    }
    ```
*   **Servicio Receptor (Ejemplo)**: Orchestrator Service (o cualquier servicio que haya invocado `execution.agent_run` y especificado una `callback_queue`).
*   **Componente Receptor (Ejemplo en Orchestrator)**: `OrchestratorService/workers/orchestrator_worker.py` (que escucharía en su cola de callbacks específica).
*   **Estado y Observaciones**:
    *   Esta es la principal forma en que AES comunica el resultado de una ejecución de agente de vuelta al solicitante.
    *   La cola de destino es completamente dinámica, definida por el cliente de AES.
    *   El `ExecutionCallbackHandler` es el responsable de construir y encolar estos mensajes. Los detalles exactos del `action_type` y la estructura final del payload dependen de su implementación.
    *   Los payloads incluyen un `ExecutionContext` para que el receptor tenga información del tenant/tier/sesión.
    *   El `ExecutionWorker` también escucha en colas como `embedding:callbacks` y `query:callbacks`, pero estas son respuestas a las solicitudes que *él mismo* (a través de sus clientes) hizo a esos servicios, y ya están cubiertas por el patrón pseudo-síncrono de dichos clientes.

---

## 2. Conversation Service

El Conversation Service es responsable de gestionar el historial de conversaciones y el contexto.

### 2.1. Interacciones Recibidas por Workers del Conversation Service

#### 2.1.1. AES (ConversationServiceClient) -> Conversation Service (ConversationWorker)

*   **Flujo General**: El `ConversationWorker` escucha en colas de acciones de su dominio (`conversation:{tenant_id}:actions`) y procesa las solicitudes delegándolas al `ConversationHandler`.
*   **Servicio Receptor**: Conversation Service
*   **Componente Receptor**: `conversation_service/workers/conversation_worker.py` (Clase `ConversationWorker`)
*   **Cola de Entrada (donde escucha el worker)**: `conversation:{tenant_id}:actions` (estándar para `BaseWorker`, el dominio es "conversation").

##### a) Procesamiento de `conversation.get_history`

*   **Acción Recibida (`action_type`)**: `conversation.get_history`
*   **Payload Esperado**: (Como se definió en la sección del `ConversationServiceClient` de AES)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "conversation.get_history",
      "task_id": "<uuid_opcional_o_no_usado_aqui>",
      "tenant_id": "string",
      "session_id": "string",
      "timestamp": "<iso_timestamp>",
      "correlation_id": "<uuid_para_respuesta_sincrona>",
      "data": {
        "limit": "integer (opcional, defecto razonable)",
        "include_system_messages": "boolean (opcional, defecto true)",
        "max_tokens": "integer (opcional, para truncar historial si es muy largo)"
      }
    }
    ```
*   **Manejo por el Worker**:
    1.  La acción es recibida por `ConversationWorker._handle_action`.
    2.  Se delega a `self.conversation_handler.handle_get_history(action, context)`.
    3.  Una vez que el handler retorna el `result`, el worker llama a `self._send_sync_response(action.correlation_id, result)`.
    4.  `_send_sync_response` publica el `result` serializado en la cola Redis: `f"conversation:responses:{action.correlation_id}"`.
*   **Payload de Respuesta (enviado a `conversation:responses:<correlation_id>`)**:
    ```json
    {
      "success": true,
      "history": [
        // Lista de mensajes, ej:
        // { "role": "user", "content": "Hola", "timestamp": "..." },
        // { "role": "assistant", "content": "Hola, ¿cómo puedo ayudarte?", "timestamp": "..." }
      ],
      "message_count": "integer"
      // ... otros campos que pueda devolver el handler
    }
    // O en caso de error:
    {
      "success": false,
      "error": {
        "type": "string",
        "message": "string"
      }
    }
    ```
*   **Observaciones y Discrepancias**:
    *   **¡DISCREPANCIA CRÍTICA EN COLA DE RESPUESTA!** El `ConversationServiceClient` (AES) espera la respuesta en `conversation:responses:get_history:<correlation_id>`. Sin embargo, el `ConversationWorker` envía la respuesta a `conversation:responses:<correlation_id>`. Esto probablemente causa que el cliente AES no reciba la respuesta y experimente un timeout.
    *   La respuesta se publica con un TTL de 60 segundos en Redis.

##### b) Procesamiento de `conversation.save_message`

*   **Acción Recibida (`action_type`)**: `conversation.save_message`
*   **Payload Esperado**: (Como se definió en la sección del `ConversationServiceClient` de AES)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "conversation.save_message",
      "task_id": "<uuid_opcional_o_no_usado_aqui>",
      "tenant_id": "string",
      "session_id": "string",
      "timestamp": "<iso_timestamp>",
      "correlation_id": "<uuid_para_respuesta_sincrona_si_wait_for_response_es_true>",
      "data": {
        "message": {
          "role": "string (user, assistant, system, tool)",
          "content": "string",
          "message_type": "string (opcional, ej. 'text', 'tool_call', 'tool_response')",
          "timestamp": "<iso_timestamp_opcional>",
          "metadata": { /* Objeto JSON para datos adicionales */ },
          "processing_time_ms": "integer (opcional)"
        },
        "wait_for_response": "boolean (indica si el cliente esperará una confirmación síncrona)"
      }
    }
    ```
*   **Manejo por el Worker**:
    1.  La acción es recibida por `ConversationWorker._handle_action`.
    2.  Se delega completamente a `self.conversation_handler.handle_save_message(action, context)`.
    3.  **Importante**: El `ConversationWorker._handle_action` *no* llama explícitamente a `_send_sync_response` para esta acción después de que el handler retorna.
*   **Respuesta Síncrona (si `data.wait_for_response` es `true`)**:
    *   **¡DISCREPANCIA CRÍTICA EN RESPUESTA SÍNCRONA!** Si se requiere una respuesta síncrona (`data.wait_for_response` es `true`), el `ConversationServiceClient` (AES) espera en `conversation:responses:save_message:<correlation_id>`. Sin embargo, la investigación del `ConversationHandler.handle_save_message` y del `ConversationWorker` muestra que **NO se envía ninguna respuesta a esta cola específica**.
    *   El `ConversationHandler.handle_save_message` simplemente procesa el guardado y devuelve un resultado al `ConversationWorker`, pero este resultado no se utiliza para enviar una respuesta síncrona a través de Redis para la acción `save_message`.
    *   Como resultado, el cliente AES que espera una confirmación síncrona para `save_message` probablemente experimentará un timeout.
*   **Payload de Respuesta Esperado por el Cliente (si `wait_for_response` es `true`, en `conversation:responses:save_message:<correlation_id>`)**:
    ```json
    {
      "success": true,
      "message_id": "<id_del_mensaje_guardado>",
      "timestamp": "<timestamp_del_guardado>"
      // ... otros campos que pueda devolver el handler
    }
    // O en caso de error:
    {
      "success": false,
      "error": {
        "type": "string",
        "message": "string"
      }
    }
    ```
*   **Observaciones**:
    *   La expectativa (basada en el cliente) de una respuesta síncrona para `save_message` no se cumple actualmente por la implementación del `ConversationHandler` y `ConversationWorker`.
    *   Si no se requiere respuesta (`wait_for_response: false`), el cliente no espera, y el `ConversationWorker` tampoco envía ninguna respuesta directa por la cola de `correlation_id`.

---

## 3. Embedding Service

El Embedding Service se encarga de generar representaciones vectoriales (embeddings) de texto.

### 3.1. Interacciones Recibidas por Workers del Embedding Service

#### 3.1.1. AES (EmbeddingClient) -> Embedding Service (EmbeddingWorker)

*   **Flujo General**: El `EmbeddingWorker` escucha en colas de acciones de su dominio (`embedding:{tenant_id}:actions`) y procesa las solicitudes. Para acciones síncronas, responde a una cola específica basada en un `correlation_id`.
*   **Servicio Receptor**: Embedding Service
*   **Componente Receptor**: `embedding_service/workers/embedding_worker.py` (Clase `EmbeddingWorker`)
*   **Cola de Entrada (donde escucha el worker)**: `embedding:{tenant_id}:actions` (estándar para `BaseWorker`, el dominio es "embedding").

##### a) Procesamiento de `embedding.generate.sync`

*   **Acción Recibida (`action_type`)**: `embedding.generate.sync` (Esta es la acción que el `EmbeddingClient` envía, aunque el worker internamente pueda parsearla como `EmbeddingGenerateAction` y luego manejarla en un método específico como `_handle_embedding_generate_sync`).
*   **Payload Esperado**: (Como se definió en la sección del `EmbeddingClient` de AES)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "embedding.generate.sync",
      "task_id": "<uuid_opcional_o_no_usado_aqui>",
      "tenant_id": "string",
      "session_id": "string (opcional)",
      "timestamp": "<iso_timestamp>",
      "data": {
        "texts": ["string1", "string2", ...],
        "model": "string (opcional, ej. 'text-embedding-ada-002')",
        "collection_id": "string (opcional)",
        "metadata": { /* Objeto JSON para datos adicionales */ },
        "correlation_id": "<uuid_para_respuesta_sincrona>", // Clave para la respuesta
        "execution_context": { /* Opcional, para pasar tenant_tier, etc. */ }
      }
    }
    ```
*   **Manejo por el Worker (`_handle_embedding_generate_sync`)**:
    1.  La acción es recibida y parseada (probablemente a `EmbeddingGenerateAction`).
    2.  Se extrae `correlation_id` de `action.data.correlation_id`.
    3.  Se construye la cola de respuesta: `response_queue = f"embedding:responses:generate:{correlation_id}"`.
    4.  La solicitud se delega al `self.embedding_handler.handle_embedding_generate(action_parseada)`.
    5.  El resultado (éxito o error) del handler se publica (usando `RPUSH`) en la `response_queue`.
    6.  Se establece un TTL de 300 segundos (5 minutos) para la `response_queue`.
*   **Payload de Respuesta (enviado a `embedding:responses:generate:<correlation_id>`)**:
    *   En caso de éxito:
        ```json
        {
          "success": true,
          "embeddings": [
            [0.1, 0.2, ...], // Embedding para texto 1
            [0.3, 0.4, ...]  // Embedding para texto 2
          ],
          "metadata": { 
            "model_used": "string", 
            "total_tokens": "integer"
            // ... otros metadatos que devuelva el handler
          }
        }
        ```
    *   En caso de error (desde el handler o una excepción en el worker):
        ```json
        {
          "success": false,
          "error": "string (descripción del error)"
        }
        ```
*   **Observaciones**:
    *   El mecanismo de solicitud-respuesta pseudo-síncrona parece estar correctamente implementado para esta interacción.
    *   La cola de respuesta utilizada por el worker (`embedding:responses:generate:<correlation_id>`) coincide con la que espera el `EmbeddingClient`.
    *   El `correlation_id` se pasa correctamente dentro del objeto `data` del `DomainAction`.

---

## 4. Query Service

El Query Service se encarga de realizar búsquedas semánticas y generación de respuestas basadas en contexto (RAG).

### 4.1. Interacciones Recibidas por Workers del Query Service

#### 4.1.1. AES (QueryClient) -> Query Service (QueryWorker)

*   **Flujo General**: El `QueryWorker` escucha en colas de acciones de su dominio (`query:{tenant_id}:actions`) y procesa las solicitudes. Para acciones síncronas, responde a una cola específica basada en un `correlation_id`.
*   **Servicio Receptor**: Query Service
*   **Componente Receptor**: `query_service/workers/query_worker.py` (Clase `QueryWorker`)
*   **Cola de Entrada (donde escucha el worker)**: `query:{tenant_id}:actions` (estándar para `BaseWorker`, el dominio es "query").

##### a) Procesamiento de `query.rag.sync` (o `query.generate.sync`)

*   **Acción Recibida (`action_type`)**: `query.rag.sync` (o su alias `query.generate.sync`).
*   **Payload Esperado**: (Como se definió en la sección del `QueryClient` de AES para `generate_rag_sync`)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "query.rag.sync", // o query.generate.sync
      "task_id": "<uuid_opcional>",
      "tenant_id": "string",
      "session_id": "string (opcional)",
      "timestamp": "<iso_timestamp>",
      "data": {
        "query_text": "string",
        "collection_id": "string",
        "model_config": { /* ... */ },
        "search_config": { /* ... */ },
        "generation_config": { /* ... */ },
        "correlation_id": "<uuid_para_respuesta_sincrona>",
        "execution_context": { /* Opcional */ }
      }
    }
    ```
*   **Manejo por el Worker (`_handle_query_generate_sync`)**:
    1.  La acción es recibida y parseada a `QueryGenerateAction`.
    2.  Se extrae `correlation_id` de `action.data.correlation_id`.
    3.  Se construye la cola de respuesta: `response_queue = f"query:responses:generate:{correlation_id}"`.
    4.  La solicitud se delega al `self.query_handler.handle_query(action_parseada)`.
    5.  El resultado (éxito o error) del handler se publica en la `response_queue`.
    6.  Se establece un TTL de 300 segundos para la `response_queue`.
*   **Payload de Respuesta (enviado a `query:responses:generate:<correlation_id>`)**:
    *   En caso de éxito:
        ```json
        {
          "success": true,
          "result": "string (respuesta generada)",
          "sources": [
            { "document_id": "...", "content_chunk": "...", "score": 0.9, ... }
          ],
          "similarity_score": "float (opcional, puede ser un score general)",
          "execution_time": "float (segundos)"
        }
        ```
    *   En caso de error:
        ```json
        {
          "success": false,
          "error": "string (descripción del error)"
        }
        ```
*   **Observaciones**:
    *   El mecanismo de solicitud-respuesta pseudo-síncrona está correctamente implementado.
    *   La cola de respuesta coincide con la esperada por el cliente.

##### b) Procesamiento de `query.search.sync`

*   **Acción Recibida (`action_type`)**: `query.search.sync`.
*   **Payload Esperado**: (Como se definió en la sección del `QueryClient` de AES para `search_documents_sync`)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "query.search.sync",
      "task_id": "<uuid_opcional>",
      "tenant_id": "string",
      "session_id": "string (opcional)",
      "timestamp": "<iso_timestamp>",
      "data": {
        "query_text": "string",
        "collection_id": "string",
        "search_config": { "top_k": 5, ... },
        "correlation_id": "<uuid_para_respuesta_sincrona>",
        "execution_context": { /* Opcional */ }
      }
    }
    ```
*   **Manejo por el Worker (`_handle_search_docs_sync`)**:
    1.  La acción es recibida y parseada a `SearchDocsAction`.
    2.  Se extrae `correlation_id` de `action.data.correlation_id`.
    3.  Se construye la cola de respuesta: `response_queue = f"query:responses:search:{correlation_id}"`.
    4.  La solicitud se delega al `self.query_handler.handle_search(action_parseada)`.
    5.  El resultado (éxito o error) del handler se publica en la `response_queue`.
    6.  Se establece un TTL de 300 segundos para la `response_queue`.
*   **Payload de Respuesta (enviado a `query:responses:search:<correlation_id>`)**:
    *   En caso de éxito:
        ```json
        {
          "success": true,
          "documents": [
            { "id": "doc1", "content": "...", "metadata": {...}, ... }
          ],
          "similarity_scores": [0.95, 0.92, ...],
          "execution_time": "float (segundos)",
          "metadata": { /* metadatos adicionales de la búsqueda */ }
        }
        ```
    *   En caso de error:
        ```json
        {
          "success": false,
          "error": "string (descripción del error)"
        }
        ```
*   **Observaciones**:
    *   El mecanismo de solicitud-respuesta pseudo-síncrona está correctamente implementado.
    *   La cola de respuesta coincide con la esperada por el cliente.

---

## 5. Agent Management Service

El Agent Management Service es responsable de gestionar las configuraciones y metadatos de los agentes.

### 5.1. Interacciones Recibidas por Workers del Agent Management Service

#### 5.1.1. AES (AgentManagementClient) -> Agent Management Service (ManagementWorker)

*   **Flujo General**: El `ManagementWorker` escucha en colas de acciones de su dominio (`management:{tenant_id}:actions`) y procesa las solicitudes.
*   **Servicio Receptor**: Agent Management Service
*   **Componente Receptor**: `agent_management_service/workers/management_worker.py` (Clase `ManagementWorker`)
*   **Cola de Entrada (donde escucha el worker)**: `management:{tenant_id}:actions` (estándar para `BaseWorker`, el dominio es "management").

##### a) Procesamiento de `agent.get_config.sync`

*   **Acción Enviada por el Cliente (`action_type`)**: `agent.get_config.sync`
*   **Payload Enviado por el Cliente**: (Como se definió en la sección del `AgentManagementClient` de AES)
    ```json
    {
      "action_id": "<uuid>",
      "action_type": "agent.get_config.sync",
      "task_id": "<uuid_opcional_o_no_usado_aqui>",
      "tenant_id": "string",
      "session_id": "string (opcional)",
      "timestamp": "<iso_timestamp>",
      "data": {
        "agent_id": "string",
        "version": "string (opcional)",
        "correlation_id": "<uuid_para_respuesta_sincrona>"
      }
    }
    ```
*   **Cola de Respuesta Esperada por el Cliente**: `agent_management:responses:get_config:<correlation_id>`
*   **Manejo por el Worker (`_handle_action` en `ManagementWorker`)**: 
    *   **DISCREPANCIA CRÍTICA**: El `ManagementWorker` actual **NO tiene un handler implementado** para la acción `agent.get_config.sync`.
    *   Cuando una acción con `action_type="agent.get_config.sync"` es recibida, el método `_handle_action` del worker entra en su bloque `else`, registra una advertencia (`No hay handler implementado para la acción: agent.get_config.sync`) y lanza un `ValueError`.
    *   Como resultado, el worker no procesa la solicitud para obtener la configuración del agente y, crucialmente, **no envía ninguna respuesta** a la cola `agent_management:responses:get_config:<correlation_id>`.
*   **Payload de Respuesta Esperado por el Cliente (pero no enviado por el worker)**:
    *   En caso de éxito (teórico):
        ```json
        {
          "success": true,
          "config": { /* ... Objeto de configuración del agente ... */ }
        }
        ```
    *   En caso de error (teórico):
        ```json
        {
          "success": false,
          "error": "string (descripción del error)"
        }
        ```
*   **Observaciones y Consecuencias**: 
    *   Debido a la falta de un handler en el `ManagementWorker` para `agent.get_config.sync`, el `AgentManagementClient` (AES) que envía esta solicitud y espera una respuesta síncrona **experimentará un timeout**.
    *   Esta es una funcionalidad rota que impide que AES obtenga dinámicamente la configuración de un agente desde el Agent Management Service.
    *   Se requiere implementar la lógica en `ManagementWorker` para manejar `agent.get_config.sync`, interactuar con el `AgentConfigHandler` (o similar) para obtener los datos, y luego enviar la respuesta a la cola `agent_management:responses:get_config:<correlation_id>` con el payload adecuado.

---

## 6. Agent Orchestrator Service

El Agent Orchestrator Service (AOS) actúa como intermediario entre los clientes finales (e.g., frontends vía WebSocket) y el Agent Execution Service (AES). Es responsable de recibir las solicitudes de chat, iniciar la ejecución de los agentes, y luego recibir los resultados finales para comunicarlos de vuelta al cliente.

### 6.1. AOS (chat_routes.py) -> Agent Execution Service (ExecutionWorker)

Esta interacción describe cómo el AOS inicia la ejecución de un agente en el AES.

*   **Flujo General**: Una solicitud API al AOS desencadena la creación de una `DomainAction` que se envía al AES.
*   **Servicio Emisor**: Agent Orchestrator Service
*   **Componente Emisor**: `agent_orchestrator_service/routes/chat_routes.py` (específicamente el endpoint `POST /api/chat/send`)
*   **Mecanismo de Envío**: `DomainQueueManager.enqueue_execution()`
*   **Servicio Receptor**: Agent Execution Service
*   **Componente Receptor**: `agent_execution_service/workers/execution_worker.py` (Clase `ExecutionWorker`)
*   **Cola de Destino (donde escucha AES)**: `execution:{tenant_id}:{tier}:actions` (la cola exacta depende del `tenant_id` y `tenant_tier` derivados del contexto de la solicitud original al AOS).
*   **Acción Enviada (`action_type`)**: `agent.execute` (implícito, ya que `ChatProcessAction` es el modelo Pydantic, pero el `ExecutionWorker` espera `agent.execute`). Se asume que `DomainQueueManager` o la lógica en `ExecutionWorker` mapea/interpreta `ChatProcessAction` adecuadamente o que el `action_type` se establece a `agent.execute` antes del envío o al recibirlo. *Nota: Se necesita confirmar el `action_type` exacto que espera `ExecutionWorker` para las ejecuciones iniciadas por AOS.* El `ExecutionWorker` maneja `execution.run`.
    *   **Actualización**: El `ChatProcessAction` es el modelo de datos. El `ExecutionWorker` en `_handle_action` espera `action_type == "execution.run"`.
*   **Payload Enviado (contenido en `ChatProcessAction` que se encola)**:
    ```json
    {
      "task_id": "<uuid_generado_por_AOS>",
      "tenant_id": "string (del header X-Tenant-ID)",
      "tenant_tier": "string (del header X-Tenant-Tier)",
      "session_id": "string (del header X-Session-ID)",
      "execution_context": { /* ... objeto ExecutionContext ... */ },
      "callback_queue": "orchestrator:<tenant_id>:callbacks", // <--- MUY IMPORTANTE
      "message": "string (mensaje del usuario)",
      "message_type": "string",
      "user_info": {}, 
      "max_iterations": null, // o int
      "timeout": 120, // o valor del contexto
      "metadata": { /* ... metadata adicional ... */ }
      // Nota: agent_id está en el execution_context
    }
    ```
*   **Respuesta Esperada**: Esta es una comunicación asíncrona. El AOS no espera una respuesta directa en este punto. La respuesta vendrá a través de la `callback_queue`.
*   **Observaciones**:
    *   El AOS (`chat_routes.py`) actúa como un cliente del AES al iniciar la ejecución.
    *   Define dinámicamente la `callback_queue` donde el AES debe enviar el resultado final.

### 6.2. AES (ExecutionWorker) -> AOS (OrchestratorWorker)

Esta interacción describe cómo el AOS recibe el resultado final de una ejecución de agente desde el AES.

*   **Flujo General**: El `ExecutionWorker` del AES, tras completar la ejecución de un agente, envía el resultado a la `callback_queue` que fue especificada por el AOS al iniciar la solicitud.
*   **Servicio Emisor**: Agent Execution Service
*   **Componente Emisor**: `agent_execution_service/workers/execution_worker.py` (Clase `ExecutionWorker`, específicamente su `ExecutionCallbackHandler`)
*   **Mecanismo de Envío**: `DomainQueueManager.enqueue_action_to_specific_queue()` (o similar, para enviar a una cola de callback directa).
*   **Servicio Receptor**: Agent Orchestrator Service
*   **Componente Receptor**: `agent_orchestrator_service/workers/orchestrator_worker.py` (Clase `OrchestratorWorker`)
*   **Cola de Entrada (donde escucha AOS)**: `orchestrator:{tenant_id}:callbacks` (esta es la cola que el `OrchestratorWorker` monitorea en su método `_process_callbacks_loop`).
*   **Acción Recibida (`action_type`)**: `execution.callback`
*   **Payload Recibido (Ejemplo)**:
    ```json
    {
        "action_id": "<uuid>",
        "action_type": "execution.callback",
        "task_id": "<uuid_original_de_la_tarea>",
        "tenant_id": "string",
        "session_id": "string",
        "timestamp": "<iso_timestamp>",
        "data": {
            "success": true, // o false
            "result": { /* ... resultado de la ejecución del agente ... */ }, // si success es true
            "error": { /* ... detalles del error ... */ } // si success es false
        }
    }
    ```
*   **Manejo por el `OrchestratorWorker`**:
    *   El método `_process_callbacks_loop` del `OrchestratorWorker` realiza un `BRPOP` en las colas `orchestrator:{tenant_id}:callbacks`.
    *   Cuando recibe un mensaje, lo deserializa.
    *   Si `action_type` es `execution.callback`, crea una `ExecutionCallbackAction`.
    *   Llama a `self.callback_handler.handle_execution_callback(action, context)`.
    *   El `CallbackHandler` (en `agent_orchestrator_service/handlers/callback_handler.py`) es entonces responsable de procesar este resultado, lo que típicamente implica enviar el mensaje/resultado final al cliente original a través del `WebSocketManager`.
*   **Observaciones**:
    *   Este es el cierre del ciclo de ejecución asíncrona iniciado por el AOS.
    *   El `OrchestratorWorker` tiene una lógica especializada (`_process_callbacks_loop`) para manejar estos callbacks directamente, separada de su ciclo de procesamiento de acciones estándar (que actualmente no maneja acciones específicas del orquestador).

---

## 7. Resumen de Discrepancias y Problemas Identificados

Durante el análisis de la comunicación inter-servicios basada en colas Redis, se han identificado las siguientes discrepancias y problemas que requieren atención:

### 7.1. AES (ConversationClient) <-> ConversationService (ConversationWorker)

*   **`conversation.get_history.sync` - Nombre de Cola de Respuesta Inconsistente**:
    *   **Problema**: El `ConversationClient` (AES) espera la respuesta en la cola `conversation:responses:get_history:<correlation_id>` (con dos puntos).
    *   El `ConversationWorker` (según análisis previo de su código fuente, específicamente el método `_send_sync_response` heredado o implementado) podría estar respondiendo a `conversation.responses.get_history.<correlation_id>` (con punto) o una variante similar si no se ha sobrescrito correctamente para usar dos puntos.
    *   **Impacto**: El cliente AES no recibirá la respuesta y probablemente experimentará un timeout.
    *   **Recomendación**: Estandarizar el nombre de la cola de respuesta. Lo más probable es que el worker deba ajustarse para usar el formato con dos puntos (`:`) que espera el cliente, ya que este es el patrón más común observado en otros servicios para colas de respuesta específicas de correlación.

*   **`conversation.save_message.sync` - Falta de Respuesta Síncrona por el Worker**:
    *   **Problema**: El `ConversationClient` (AES) tiene una opción para esperar una confirmación síncrona (`wait_for_confirmation=True`) para la acción `conversation.save_message.sync`, esperando una respuesta en `conversation:responses:save_message:<correlation_id>`.
    *   El `ConversationWorker` actualmente no parece implementar el envío de una respuesta a esta cola de callback específica tras procesar `save_message`.
    *   **Impacto**: Si AES usa `wait_for_confirmation=True`, no recibirá respuesta y experimentará un timeout.
    *   **Recomendación**: Implementar en `ConversationWorker` la lógica para enviar una respuesta (éxito/error) a la cola `conversation:responses:save_message:<correlation_id>` cuando se procesa una acción `conversation.save_message.sync` que incluye un `correlation_id` para respuesta síncrona.

### 7.2. AES (AgentManagementClient) <-> AgentManagementService (ManagementWorker)

*   **`agent.get_config.sync` - Handler No Implementado en el Worker**:
    *   **Problema**: El `AgentManagementClient` (AES) envía la acción `agent.get_config.sync` y espera una respuesta síncrona en la cola `agent_management:responses:get_config:<correlation_id>`.
    *   El `ManagementWorker` no tiene un handler (case) en su método `_handle_action` para `agent.get_config.sync`. Como resultado, la acción no se procesa y no se envía ninguna respuesta.
    *   **Impacto**: AES no puede obtener la configuración del agente y experimentará un timeout, lo que es una funcionalidad crítica rota.
    *   **Recomendación**: Implementar un handler en `ManagementWorker` para la acción `agent.get_config.sync`. Este handler debería: 
        1.  Extraer el `agent_id` y `correlation_id` del payload.
        2.  Interactuar con la lógica de negocio correspondiente (e.g., `AgentConfigHandler`) para obtener la configuración del agente.
        3.  Construir un payload de respuesta (éxito/error).
        4.  Publicar la respuesta en la cola `agent_management:responses:get_config:<correlation_id>`.

### 7.3. Verificación de `action_type` para `ExecutionWorker`

*   **Contexto**: El `AgentOrchestratorService` (específicamente `chat_routes.py`) encola una `ChatProcessAction` para ser procesada por el `AgentExecutionService`.
*   **Posible Problema Leve**: La documentación indica que el `action_type` que el `ExecutionWorker` espera para iniciar una ejecución es `execution.run`. El objeto `ChatProcessAction` en sí mismo no define explícitamente su `action_type` como `execution.run` en su modelo Pydantic, sino que es un modelo de datos para la solicitud.
*   **Clarificación**: Es probable que el `DomainQueueManager.enqueue_execution` o la lógica dentro del `BaseWorker` del `ExecutionWorker` (antes de llegar a `_handle_action`) establezca o interprete correctamente el `action_type` a `execution.run` basado en el dominio de destino y la naturaleza de la acción. Sin embargo, esto es una suposición.
*   **Recomendación**: Confirmar que la `ChatProcessAction` enviada por AOS resulta efectivamente en una acción con `action_type="execution.run"` cuando es recibida y procesada por el `ExecutionWorker`.

### 7.4. Direccionamiento de Colas de Respuesta (General)

*   **Observación**: Se ha notado una inconsistencia en el uso de `.` vs. `:` en los nombres de las colas de respuesta síncronas (e.g., `conversation:responses:get_history:<cid>` vs. `conversation.responses.get_history.<cid>`).
*   **Recomendación**: Estandarizar a un solo formato, preferiblemente usando `:` como separador para mantener la coherencia con la nomenclatura general de Redis y otros patrones observados en el proyecto (e.g., `domain:tenant_id:tier:actions`). La mayoría de los clientes parecen esperar el formato con `:`.

---

## 8. Ingestion Service <-> Embedding Service

Esta sección describe cómo el `IngestionService` solicita la generación de embeddings al `EmbeddingService` y cómo recibe los resultados.

### 8.1. IngestionService (EmbeddingClient) -> EmbeddingService (API)

Esta interacción detalla cómo el `IngestionService` envía los chunks de texto al `EmbeddingService` para su vectorización.

*   **Flujo General**: El `IngestionWorker`, después de procesar y fragmentar un documento, utiliza su `EmbeddingClient` para enviar una solicitud HTTP al `EmbeddingService`.
*   **Servicio Emisor**: Ingestion Service
*   **Componente Emisor**: `ingestion_service.clients.EmbeddingClient` (método `generate_embeddings`)
*   **Mecanismo de Envío**: Llamada HTTP POST.
*   **Servicio Receptor**: Embedding Service
*   **Componente Receptor**: Endpoint API del `EmbeddingService` (presumiblemente `POST /api/v1/embeddings/generate`).
*   **URL de Destino**: `f"{settings.EMBEDDING_SERVICE_URL}/api/v1/embeddings/generate"` (configurado en `IngestionService`).
*   **Payload Enviado (JSON, basado en `EmbeddingRequestAction` del `IngestionService`)**:
    ```json
    {
      "document_id": "string",
      "collection_id": "string",
      "tenant_id": "string",
      "chunks": [ { "chunk_id": "string", "text": "string", "metadata": {} } ],
      "model": "string (e.g., text-embedding-ada-002)",
      "task_id": "string (ID de la tarea de ingesta)",
      "callback_queue": "ingestion:callbacks:embedding" // o el valor de settings.EMBEDDING_CALLBACK_QUEUE
    }
    ```
*   **Respuesta HTTP Esperada por `EmbeddingClient`**: `202 Accepted`. Esto significa que el `EmbeddingService` ha recibido la solicitud y la procesará asíncronamente.
*   **Observaciones**:
    *   A diferencia de otras comunicaciones internas que usan Redis directamente para la solicitud, aquí se usa una API HTTP.
    *   El `IngestionService` especifica una `callback_queue` en el payload para que el `EmbeddingService` sepa dónde enviar el resultado.

### 8.2. AgentExecutionService -> EmbeddingService (Generación Síncrona de Embeddings)

El `AgentExecutionService` puede necesitar generar embeddings de forma síncrona (o pseudo-síncrona) para ciertas operaciones, como procesar una consulta de usuario en tiempo real antes de interactuar con un LLM.

*   **Servicio Emisor**: `AgentExecutionService`
*   **Componente Emisor**: `agent_execution_service.clients.embedding_client.EmbeddingClient` (método `generate_embeddings_sync`)
*   **Servicio Receptor**: `EmbeddingService`
*   **Componente Receptor**: `embedding_service.workers.embedding_worker.EmbeddingWorker` (método `_handle_embedding_generate_sync`)
*   **Acción de Dominio**: `embedding.generate.sync`
*   **Mecanismo de Comunicación**: Pseudo-síncrono sobre Redis.
    1.  El `EmbeddingClient` del AES crea un `correlation_id` único y una cola de respuesta específica (ej: `embedding:responses:generate:<correlation_id>`).
    2.  Envía una `DomainAction` de tipo `embedding.generate.sync` a la cola principal del `EmbeddingService` (`embedding.actions`), incluyendo el `correlation_id` en los datos de la acción.
    3.  El `EmbeddingClient` realiza una espera bloqueante (`BLPOP`) en la cola de respuesta específica.
    4.  El `EmbeddingWorker` del `EmbeddingService` procesa la acción `embedding.generate.sync`.
    5.  En lugar de enviar un callback a una cola genérica, el `EmbeddingWorker` publica el resultado (embeddings o error) directamente en la cola de respuesta identificada por el `correlation_id`.
    6.  El `EmbeddingClient` recibe la respuesta y la devuelve al llamador en AES.
*   **Propósito**: Obtener embeddings para textos de manera bloqueante, simplificando el flujo en AES cuando se requiere el resultado inmediato.
*   **Payload Principal (`embedding.generate.sync` data)**:
    *   `texts`: Lista de textos a convertir en embeddings.
    *   `tenant_id`, `session_id`.
    *   `correlation_id`: Para que `EmbeddingService` sepa dónde responder.
    *   `model` (opcional), `collection_id` (opcional), `metadata` (opcional).
*   **Respuesta**: Los embeddings generados o un error, devueltos directamente a través de la cola de respuesta específica.

### 8.3. EmbeddingService (EmbeddingWorker) -> IngestionService (IngestionWorker) (Callback)

Esta interacción describe cómo el `EmbeddingService` devuelve los embeddings generados (o un error) al `IngestionService`.

*   **Flujo General**: Después de que el `EmbeddingService` genera los embeddings, envía una acción de callback a la cola especificada por el `IngestionService` en la solicitud original.
*   **Servicio Emisor**: Embedding Service
*   **Componente Emisor**: `embedding_service.workers.EmbeddingWorker` (o la lógica que maneja la acción `embedding.generate.sync` o la solicitud HTTP).
*   **Mecanismo de Envío**: `DomainQueueManager.enqueue_action_to_specific_queue()` (o equivalente, para publicar en una cola específica).
*   **Servicio Receptor**: Ingestion Service
*   **Componente Receptor**: `ingestion_service.workers.IngestionWorker` (método `_handle_embedding_callback` escuchando en `settings.EMBEDDING_CALLBACK_QUEUE`).
*   **Cola de Destino (donde escucha `IngestionWorker`)**: El valor de `settings.EMBEDDING_CALLBACK_QUEUE` del `IngestionService` (e.g., `ingestion:callbacks:embedding`).
*   **Acción/Payload Enviado (Ejemplo basado en `EmbeddingCallbackAction` del `IngestionService`)**:
    ```json
    {
      "task_id": "string (ID original de la tarea de ingesta)",
      "document_id": "string",
      "collection_id": "string",
      "tenant_id": "string",
      "status": "success", // o "error"
      "embeddings": [ /* lista de vectores o datos de embeddings */ ], // si success
      "error_message": "string", // si error
      "error_code": "string" // si error
    }
    ```
*   **Manejo por el `IngestionWorker`**:
    *   El `IngestionWorker` deserializa el mensaje a una `EmbeddingCallbackAction`.
    *   Si `status` es `success`, procede a almacenar los embeddings (TODO actual: guardar en BD vectorial).
    *   Actualiza el estado de la tarea de ingesta y notifica al cliente final vía WebSockets.
*   **Observaciones**:
    *   La respuesta es asíncrona y utiliza colas Redis, cerrando el ciclo iniciado por la solicitud HTTP.

---

## 9. AgentExecutionService (AES) -> QueryService (QS)

Esta sección describe cómo el `AgentExecutionService` utiliza el `QueryService` para realizar búsquedas de documentos y generación de respuestas aumentadas por recuperación (RAG) como parte de la ejecución de un agente.

*   **Servicio Emisor**: Agent Execution Service (AES)
*   **Componente Emisor**: `agent_execution_service.clients.QueryClient`
*   **Servicio Receptor**: Query Service (QS)
*   **Componente Receptor**: `query_service.workers.QueryWorker`
*   **Mecanismo de Comunicación**: Acciones de Dominio encoladas en Redis, con un patrón de respuesta pseudo-síncrono utilizando colas de respuesta específicas por `correlation_id`.
*   **Cola de Acciones (donde QS escucha)**: `query.actions`

### 9.1. Generación RAG (Búsqueda + Generación LLM)

*   **Método en Cliente AES**: `QueryClient.generate_rag_sync()`
*   **Acción Enviada**: `query.rag.sync`
*   **Payload Principal Enviado**:
    ```json
    {
      "query": "string (pregunta del usuario)",
      "session_id": "string",
      "collection_ids": ["string"],
      "llm_model": "string (opcional)",
      "search_limit": "integer (opcional)",
      "metadata": {},
      "correlation_id": "string (uuid único para la respuesta)"
    }
    ```
*   **Flujo de Respuesta**:
    1.  AES (`QueryClient`) publica la acción `query.rag.sync` en la cola `query.actions`.
    2.  AES espera (con `BLPOP`) una respuesta en una cola Redis temporal y única: `query:responses:generate:{correlation_id}`.
    3.  QS (`QueryWorker`) procesa la acción, realiza la búsqueda vectorial, interactúa con un LLM para generar la respuesta, y luego publica el resultado en la cola de respuesta especificada por `correlation_id`.
    4.  AES recibe la respuesta y la devuelve al flujo de ejecución del agente.
*   **Propósito**: Permitir que un agente obtenga una respuesta completa basada en conocimiento externo.

### 9.2. Búsqueda de Documentos (Solo Búsqueda)

*   **Método en Cliente AES**: `QueryClient.search_documents_sync()`
*   **Acción Enviada**: `query.search.sync` (inferido, coincide con `QueryWorker`)
*   **Payload Principal Enviado (probable)**:
    ```json
    {
      "query": "string (pregunta del usuario)",
      "collection_ids": ["string"],
      "search_limit": "integer (opcional)",
      "correlation_id": "string (uuid único para la respuesta)"
    }
    ```
*   **Flujo de Respuesta**: Similar a `generate_rag_sync`, pero el QS solo realiza la búsqueda y devuelve los documentos encontrados, sin el paso de generación con LLM.
*   **Propósito**: Permitir que un agente recupere documentos relevantes que pueden ser usados para otros propósitos dentro de la lógica del agente (e.g., resumir, extraer información específica, etc.).

---

## 10. QueryService (QS) <-> EmbeddingService (ES) (Generación de Embeddings para Consultas)

Esta sección describe cómo el `QueryService` puede solicitar la generación de embeddings al `EmbeddingService`, típicamente para convertir la consulta de un usuario en un vector antes de realizar una búsqueda por similitud en la base de datos vectorial. También cubre cómo el `EmbeddingService` devuelve el resultado.

### 10.1. QueryService (QS) -> EmbeddingService (ES): Solicitud de Embeddings

*   **Servicio Emisor**: Query Service (QS)
*   **Componente Emisor**: `query_service.clients.EmbeddingClient` (método `generate_embeddings`)
*   **Servicio Receptor**: Embedding Service (ES)
*   **Componente Receptor**: `embedding_service.workers.EmbeddingWorker` (manejando la acción correspondiente, e.g., `embedding.generate.sync`)
*   **Mecanismo de Envío**: `DomainQueueManager.enqueue_execution()` para encolar una `EmbeddingGenerateAction` en el dominio `embedding`.
*   **Payload Principal Enviado (`EmbeddingGenerateAction`)**:
    ```json
    {
      "task_id": "string (uuid)",
      "tenant_id": "string",
      "tenant_tier": "string",
      "session_id": "string",
      "execution_context": { /* ... */ },
      "callback_queue": "string (e.g., query:callbacks:embedding:{unique_id})", // Cola donde QS espera la respuesta
      "texts": ["string (texto de la consulta del usuario u otros textos)"],
      "model": "string (opcional, modelo de embedding)",
      "metadata": {}
    }
    ```
*   **Propósito**: El `QueryService` necesita convertir texto (principalmente la consulta del usuario) en un vector para poder realizar búsquedas semánticas en la base de datos vectorial.

### 10.2. EmbeddingService (ES) -> QueryService (QS): Callback con Embeddings

*   **Servicio Emisor**: Embedding Service (ES)
*   **Componente Emisor**: `embedding_service.workers.EmbeddingWorker` (o lógica de procesamiento de `EmbeddingGenerateAction`).
*   **Servicio Receptor**: Query Service (QS)
*   **Componente Receptor**: `query_service.workers.QueryWorker` (método `_handle_action` para `action_type="embedding.callback"` a través de `EmbeddingCallbackHandler`).
*   **Mecanismo de Envío**: El `EmbeddingService` publica una acción de respuesta (el callback) en la `callback_queue` especificada por el `QueryService` en la solicitud original.
*   **Acción/Payload de Callback Esperado por QS (Ejemplo)**:
    ```json
    {
      "action_type": "embedding.callback", // O un tipo más específico si EmbeddingCallbackHandler lo espera
      "task_id": "string (ID original de la solicitud de embedding)",
      "status": "success", // o "error"
      "embeddings": [ /* lista de vectores */ ], // si success
      "error_message": "string" // si error
      // ... otros campos relevantes del callback
    }
    ```
*   **Manejo por el `QueryWorker`**:
    *   El `QueryWorker` (a través de su `EmbeddingCallbackHandler`) procesa este callback.
    *   Utiliza los embeddings recibidos para continuar con el flujo de procesamiento de la consulta original (e.g., realizar la búsqueda por similitud en la base de datos vectorial usando el embedding de la consulta).
*   **Propósito**: Cerrar el ciclo de la solicitud de embeddings, permitiendo al `QueryService` proceder con la consulta del usuario.

---

## 11. AgentManagementService (AMS) -> IngestionService (IS)

Esta sección describe cómo el `AgentManagementService` interactúa con el `IngestionService` para validar y listar colecciones de documentos, lo cual es relevante al configurar agentes que utilizan dichas colecciones como fuentes de conocimiento.

*   **Servicio Emisor**: Agent Management Service (AMS)
*   **Componente Emisor**: `agent_management_service.clients.IngestionClient`
*   **Servicio Receptor**: Ingestion Service (IS)
*   **Componente Receptor**: Endpoints API del `IngestionService`.
*   **Mecanismo de Comunicación**: Llamadas HTTP API.

### 11.1. Validar Colecciones

*   **Método en Cliente AMS**: `IngestionClient.validate_collections()`
*   **Endpoint API en IS**: `POST /api/v1/collections/validate`
*   **Payload Enviado por AMS**:
    ```json
    {
      "collection_ids": ["string (ID de colección 1)", "string (ID de colección 2)"]
    }
    ```
*   **Headers Enviados por AMS**: `X-Tenant-ID: string`
*   **Respuesta Esperada por AMS (de IS)**:
    ```json
    {
      "valid": true, // o false
      "invalid_ids": ["string (ID de colección inválida si alguna)"]
    }
    ```
*   **Propósito**: Antes de asociar colecciones a un agente, el AMS verifica que estas colecciones existan y sean válidas en el `IngestionService` para el tenant especificado.

### 11.2. Listar Colecciones

*   **Método en Cliente AMS**: `IngestionClient.list_collections()`
*   **Endpoint API en IS**: `GET /api/v1/collections`
*   **Headers Enviados por AMS**: `X-Tenant-ID: string`
*   **Respuesta Esperada por AMS (de IS)**:
    ```json
    {
      "collections": [
        { "id": "string", "name": "string", "description": "string", /* otros metadatos */ }
      ]
    }
    ```
*   **Propósito**: El AMS puede obtener una lista de todas las colecciones disponibles para un tenant, por ejemplo, para mostrar en una interfaz de usuario donde se configuran los agentes.

---

## 12. AgentManagementService (AMS) -> AgentExecutionService (AES)

Esta sección describe cómo el `AgentManagementService` notifica al `AgentExecutionService` para invalidar la caché de configuración de un agente. Esto es crucial cuando la configuración de un agente se actualiza en AMS, para asegurar que AES utilice la versión más reciente.

*   **Servicio Emisor**: Agent Management Service (AMS)
*   **Componente Emisor**: `agent_management_service.clients.ExecutionClient`
*   **Servicio Receptor**: Agent Execution Service (AES)
*   **Componente Receptor**: Endpoint API interno del `AgentExecutionService`.
*   **Mecanismo de Comunicación**: Llamada HTTP API.

### 12.1. Invalidar Caché de Agente

*   **Método en Cliente AMS**: `ExecutionClient.invalidate_agent_cache()`
*   **Endpoint API en AES**: `POST /internal/cache/invalidate/{agent_id}` (donde `{agent_id}` es el ID del agente cuya caché se debe invalidar).
*   **Headers Enviados por AMS**: `X-Tenant-ID: string`
*   **Respuesta Esperada por AMS (de AES)**: Un código de estado HTTP `200 OK` si la invalidación fue exitosa.
*   **Propósito**: Cuando un agente es modificado (e.g., sus herramientas, prompts, o configuración de colecciones cambian) o eliminado en AMS, se envía esta solicitud a AES para que elimine de su caché la configuración antigua de ese agente. Esto fuerza a AES a solicitar la configuración actualizada de AMS (a través de la acción `agent.get_config.sync`) la próxima vez que necesite ejecutar dicho agente.

---

## 13. ConversationService: Funcionalidad de Migración de Datos (MigrationWorker)

El `ConversationService` incluye un `MigrationWorker` responsable de migrar datos de conversaciones desde un almacenamiento temporal (Redis) a una base de datos persistente (PostgreSQL). Esta funcionalidad es crucial para la persistencia a largo plazo de los datos de conversación.

*   **Servicio Contenedor**: `ConversationService`
*   **Componente Principal**: `conversation_service.workers.MigrationWorker`
*   **Propósito Principal**: Migrar datos de conversación de Redis a PostgreSQL, tanto de forma automática como bajo demanda.

### 13.1. Modos de Operación

El `MigrationWorker` opera en dos modos:

1.  **Modo Automático/Proactivo**:
    *   El worker ejecuta un ciclo de migración (`_migration_loop`) en segundo plano de forma periódica (intervalo configurable vía `settings.persistence_migration_interval`).
    *   En cada ciclo, intenta migrar un lote de conversaciones de Redis a PostgreSQL utilizando el `PersistenceManager` (método `migrate_batch_to_postgresql()`).
    *   Este modo asegura una migración continua de datos sin intervención manual.

2.  **Modo Reactivo (mediante Domain Actions)**:
    *   El worker puede procesar acciones de dominio específicas encoladas a él (dominio: `conversation`) para controlar el proceso de migración o migrar datos específicos.
    *   **Acciones de Dominio Soportadas**:
        *   `migration.start`:
            *   **Payload**: N/A
            *   **Descripción**: Inicia (o reinicia) manualmente el ciclo de migración automática (`_migration_loop`).
        *   `migration.stop`:
            *   **Payload**: N/A
            *   **Descripción**: Detiene manualmente el ciclo de migración automática.
        *   `migration.migrate_conversation`:
            *   **Payload**: `{"conversation_id": "string (ID de la conversación a migrar)", "cleanup_memory": true/false (opcional, default true)}`
            *   **Descripción**: Solicita la migración de una conversación específica de Redis a PostgreSQL. Si `cleanup_memory` es `true`, también invoca al `MemoryManager` para limpiar datos asociados a esa conversación en Redis después de una migración exitosa.
        *   `migration.get_stats`:
            *   **Payload**: N/A
            *   **Descripción**: Solicita estadísticas sobre el proceso de migración (e.g., cuántas conversaciones migradas, pendientes, etc.).

### 13.2. Interacciones y Dependencias Clave

Dentro del `ConversationService`, el `MigrationWorker` interactúa principalmente con:

*   **`PersistenceManager`**: Este servicio es el encargado de la lógica de bajo nivel para leer datos de conversaciones de Redis y escribirlos en PostgreSQL. Es utilizado tanto por el ciclo automático como por la acción `migration.migrate_conversation`.
*   **`MemoryManager`**: Utilizado por la acción `migration.migrate_conversation` para limpiar datos de la memoria (Redis) una vez que una conversación ha sido persistida en PostgreSQL.
*   **Bases de Datos**: Directamente (a través del `PersistenceManager`) con Redis (fuente) y PostgreSQL (destino).

### 13.3. Iniciación de Acciones de Dominio

Si bien el ciclo automático se ejecuta tras el inicio del worker, las acciones de dominio explícitas (como `migration.start` o `migration.migrate_conversation`) no parecen ser iniciadas a través de APIs HTTP estándar del `ConversationService`. Se presume que estas acciones son encoladas mediante:

*   **Scripts de Línea de Comandos (CLI)**: Herramientas administrativas o scripts de mantenimiento podrían ser utilizados para encolar estas acciones directamente a la cola del dominio `conversation`.
*   **Otros procesos internos o tareas programadas** que requieran control sobre el flujo de migración.

---

## 14. IngestionService -> WebSocket (Cliente / AgentOrchestratorService)

El `IngestionService` utiliza WebSockets para enviar actualizaciones en tiempo real sobre el progreso del procesamiento de documentos y la generación de embeddings. Estas actualizaciones permiten a los clientes (ya sea un frontend directamente o a través del `AgentOrchestratorService`) monitorear el estado de las tareas de ingesta.

*   **Servicio Emisor**: `IngestionService`
*   **Componente Emisor**: `ingestion_service.websockets.event_dispatcher` (utilizado por `IngestionWorker`)
*   **Servicio Receptor Potencial**: `AgentOrchestratorService` (actuando como proxy WebSocket) o directamente un cliente Frontend.
*   **Mecanismo de Comunicación**: Mensajes WebSocket.
*   **Propósito**: Proveer feedback en tiempo real sobre el ciclo de vida de una tarea de ingesta.

### 14.1. Tipos de Mensajes WebSocket Enviados

El `IngestionWorker` envía varios tipos de mensajes a través del `event_dispatcher`:

1.  **Actualizaciones de Estado de Tarea (`TaskStatusUpdate`)**:
    *   **Cuándo se envía**: Al iniciar el procesamiento, al finalizar (éxito, error, cancelación), o al cambiar el estado general de la tarea.
    *   **Contenido Típico**: `task_id`, `tenant_id`, `current_status` (e.g., `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`), `message` descriptivo.

2.  **Hitos de Procesamiento (`ProcessingMilestone`)**:
    *   **Cuándo se envía**: En puntos clave del procesamiento del documento, como "documento recibido", "texto extraído", "chunks generados", "embeddings solicitados", "embedding recibido para chunk X".
    *   **Contenido Típico**: `task_id`, `tenant_id`, `milestone` (un identificador del hito), `message`, `percentage` (progreso estimado), `details` (información adicional específica del hito).

3.  **Notificación de Error de Tarea (`TaskError`)**:
    *   **Cuándo se envía**: Si ocurre un error irrecuperable durante el procesamiento de la tarea.
    *   **Contenido Típico**: `task_id`, `tenant_id`, `error_message`, `error_details`.

4.  **Confirmación de Cancelación (`TaskCancelled`)**:
    *   **Cuándo se envía**: Después de que una solicitud de cancelación (`TaskCancelAction`) es procesada.
    *   **Contenido Típico**: `task_id`, `tenant_id`, `message` confirmando la cancelación.

### 14.2. Flujo General

*   Cuando el `IngestionWorker` comienza a procesar una `DocumentProcessAction`, o cuando maneja un `EmbeddingCallbackAction` o una `TaskStatusAction`/`TaskCancelAction`, utiliza el `event_dispatcher` para enviar la información relevante al cliente WebSocket conectado.
*   Esto permite que la interfaz de usuario refleje el progreso de la ingesta sin necesidad de sondeos (polling) constantes.

---

## 15. Cliente API -> IngestionService (Inicio del Proceso de Ingesta)

El proceso de ingesta de documentos en el `IngestionService` se inicia cuando un cliente (que puede ser otro microservicio, una interfaz de usuario, o un script) realiza una solicitud HTTP a los endpoints API expuestos por el `IngestionService`.

*   **Servicio Emisor**: Cliente API (no especificado, puede ser cualquier servicio o herramienta externa)
*   **Servicio Receptor**: `IngestionService`
*   **Componente Receptor**: Endpoints API definidos en `ingestion_service.routes.documents`.
*   **Mecanismo de Comunicación**: Llamadas HTTP API.
*   **Propósito**: Enviar un documento (archivo, URL o texto plano) al `IngestionService` para su procesamiento, fragmentación y eventual generación de embeddings.

### 15.1. Endpoints API Principales para Ingesta

El `IngestionService` expone varios endpoints para iniciar la ingesta:

1.  **`POST /api/v1/documents/`** (Endpoint Genérico)
    *   **Descripción**: Permite la ingesta de un documento proporcionando un archivo (`multipart/form-data`), una URL o texto plano como parte de los parámetros de la solicitud.
    *   **Parámetros Clave**: `tenant_id`, `collection_id`, `document_id`, `file` (opcional), `url` (opcional), `text` (opcional), `title`, `chunk_size`, etc.
    *   **Acción Interna**: Al recibir una solicitud válida, este endpoint:
        1.  Crea una `DocumentProcessAction` con los detalles de la solicitud.
        2.  Encola esta acción en la cola `settings.DOCUMENT_QUEUE` utilizando el `queue_service`.
        3.  Responde al cliente con un `TaskResponse` que incluye un `task_id` para el seguimiento.

2.  **`POST /api/v1/documents/text`** (Para Texto Plano)
    *   **Descripción**: Especializado para la ingesta de texto plano enviado en el cuerpo JSON de la solicitud.
    *   **Payload JSON**: Incluye `tenant_id`, `collection_id`, `document_id`, `text`, etc.
    *   **Acción Interna**: Similar al endpoint genérico, crea y encola una `DocumentProcessAction`.

3.  **`POST /api/v1/documents/url`** (Para URLs)
    *   **Descripción**: Especializado para la ingesta de contenido desde una URL enviada en el cuerpo JSON.
    *   **Payload JSON**: Incluye `tenant_id`, `collection_id`, `document_id`, `url`, etc.
    *   **Acción Interna**: Similar al endpoint genérico, crea y encola una `DocumentProcessAction`.

### 15.2. Flujo Desencadenado

Una vez que la `DocumentProcessAction` es encolada:

*   El `IngestionWorker` del `IngestionService` consume esta acción de la cola `settings.DOCUMENT_QUEUE`.
*   Esto inicia el pipeline de procesamiento de documentos dentro del `IngestionWorker`, que incluye la fragmentación, la solicitud de embeddings al `EmbeddingService` (Sección 8 y `ingestion_embedding_communication.md`), y el envío de actualizaciones de progreso vía WebSocket (Sección 14).

Esta interacción API es el punto de entrada principal para toda la funcionalidad de ingesta de documentos del sistema.

---

## 16. Funcionalidad Pendiente: Almacenamiento de Embeddings (IngestionService)

Durante el análisis del `IngestionService`, se observó que después de que el `IngestionWorker` recibe los embeddings generados por el `EmbeddingService` (a través de la interacción descrita en la Sección 8.2 y en el documento `ingestion_embedding_communication.md`), existe un paso crucial que actualmente está marcado como pendiente:

*   **Componente Involucrado**: `ingestion_service.workers.IngestionWorker`
*   **Método Específico**: `_handle_embedding_callback`
*   **Código Relevante**:
    ```python
    # Dentro de _handle_embedding_callback, después de recibir embeddings exitosamente:
    # TODO: Guardar embeddings en base de datos vectorial
    # Simulamos almacenamiento
    await asyncio.sleep(1)
    
    # Marcar tarea como completada
    # ... (código para actualizar estado y notificar al cliente)
    ```

*   **Descripción del Problema/Funcionalidad Pendiente**:
    *   El `IngestionService` completa exitosamente la extracción de texto, la fragmentación (chunking) y la obtención de embeddings para los chunks.
    *   Sin embargo, el paso final de almacenar estos chunks y sus correspondientes embeddings en una base de datos vectorial (para que luego puedan ser consultados por el `QueryService`) no está implementado.
    *   Las búsquedas de código dentro del `IngestionService` no revelaron ningún cliente o mecanismo existente para interactuar con una base de datos vectorial o con el `QueryService` para este propósito.
    *   El `QueryService` tampoco expone una API de escritura obvia ni maneja acciones encoladas para la indexación de nuevos documentos/embeddings.

*   **Impacto**:
    *   Sin este paso, los documentos procesados por el `IngestionService` no estarán disponibles para las búsquedas RAG (Retrieval-Augmented Generation) que realiza el `QueryService`.
    *   El ciclo de ingesta de conocimiento queda incompleto.

*   **Posibles Soluciones (Especulativo)**:
    1.  **API en `QueryService`**: El `QueryService` podría exponer un endpoint API (e.g., `/api/v1/vectorstore/index`) que el `IngestionWorker` llamaría, enviando los chunks y sus embeddings.
    2.  **Acción para `QueryWorker`**: Definir una nueva `DomainAction` (e.g., `query.index_documents.sync`) que el `IngestionWorker` encolaría para el `QueryService`. El `QueryWorker` necesitaría un nuevo handler para procesar esta acción y escribir en la base de datos vectorial.
    3.  **Cliente de BD Vectorial en `IngestionService`**: El `IngestionService` podría integrar directamente un cliente para la base de datos vectorial específica que se esté utilizando (e.g., ChromaDB, Pinecone, Weaviate) y realizar la escritura él mismo.

*   **Estado Actual**: Esta funcionalidad es un `TODO` y representa una brecha en el flujo de datos de ingesta para RAG.

---

### 14. AgentExecutionService -> ConversationService

Esta interacción se centra en la gestión del historial de conversaciones.

*   **Acción de Dominio**: `conversation.save_message`
*   **Emisor**: `AgentExecutionService` (específicamente `agent_execution_service.clients.conversation_client.ConversationClient`)
*   **Receptor**: `ConversationService` (específicamente `conversation_service.workers.conversation_worker.ConversationWorker`)
*   **Cola Predeterminada**: `conversation:{tenant_id}:actions` (siguiendo el patrón estándar de `DomainQueueManager`)
*   **Propósito**: Persistir un mensaje (ya sea del usuario o la respuesta del agente) en el historial de la conversación asociada a una sesión.
*   **Payload Típico (Ejemplo)**:
    ```json
    {
        "action_type": "conversation.save_message",
        "tenant_id": "some_tenant_id",
        "session_id": "some_session_id",
        "message": {
            "sender": "user" / "agent",
            "content": "Texto del mensaje",
            "timestamp": "2023-10-27T10:30:00Z",
            "metadata": {}
        },
        "execution_context": { ... }
    }
    ```
*   **Implementación Actual**:
    *   El `ConversationClient` en `AgentExecutionService` contiene la lógica para construir y encolar la `DomainAction` `conversation.save_message`.
    *   El `ConversationWorker` en `ConversationService` tiene un handler dedicado en su método `_handle_action` para procesar esta acción, interactuando con el `ConversationHandler` para guardar el mensaje en la base de datos (actualmente Redis, con planes de migrar a PostgreSQL).
*   **Notas Adicionales**:
    *   El `ConversationWorker` también está preparado para manejar las acciones `conversation.get_context` y `conversation.session_closed`.
    *   Sin embargo, las búsquedas de código (`grep`) no han revelado clientes en otros servicios que estén enviando activamente estas dos acciones al `ConversationService` en este momento. Podrían ser funcionalidades en desarrollo, para uso interno, o parte de flujos aún no analizados.

### 15. Callbacks Asíncronos hacia AgentExecutionService

El `AgentExecutionService` (AES), a través de su `ExecutionWorker`, está preparado para recibir callbacks asíncronos de otros servicios, específicamente del `EmbeddingService` y del `QueryService`. Sin embargo, la utilización actual de estos mecanismos de callback por parte de los clientes dentro del propio AES presenta ciertas particularidades.

#### 15.1. EmbeddingService -> AgentExecutionService (Callback)

*   **Acción de Dominio**: `embedding.callback`
*   **Emisor Potencial**: `EmbeddingService`
*   **Receptor**: `AgentExecutionService` (específicamente `agent_execution_service.workers.execution_worker.ExecutionWorker`, que delega a `agent_execution_service.handlers.embedding_callback_handler.EmbeddingCallbackHandler`)
*   **Cola Predeterminada**: `embedding:callbacks` (el `ExecutionWorker` está configurado para escuchar en esta cola además de sus colas de acciones estándar)
*   **Propósito Teórico**: Notificar al `AgentExecutionService` sobre la finalización (exitosa o con error) de una solicitud de generación de embeddings que AES habría iniciado de forma asíncrona.
*   **Payload Típico (Ejemplo de `EmbeddingCallbackAction`)**:
    ```json
    {
        "action_type": "embedding.callback",
        "tenant_id": "some_tenant_id",
        "task_id": "original_embedding_request_task_id",
        "status": "completed",
        "result": {
            "embeddings": [[0.1, 0.2], ...],
            "model": "text-embedding-ada-002",
            "dimensions": 1536,
            "total_tokens": 120,
            "processing_time": 0.5
        },
        "execution_context": { ... }
    }
    ```
*   **Mecanismo de Manejo en AES**:
    *   El `ExecutionWorker` consume la acción de la cola `embedding:callbacks`.
    *   Delega el procesamiento al `EmbeddingCallbackHandler`.
    *   El `EmbeddingCallbackHandler` está diseñado para un patrón de **espera activa**:
        1.  Al recibir el callback, almacena el resultado (o error) asociado al `task_id` de la acción original.
        2.  Notifica a una corrutina que podría estar esperando este resultado mediante `asyncio.Event`.
        3.  El handler expone un método `wait_for_embedding_result(task_id, timeout)` que una parte del código de AES (el iniciador de la solicitud asíncrona) llamaría para obtener el resultado del embedding.
*   **Estado Actual de la Implementación**:
    *   Si bien el `ExecutionWorker` y el `EmbeddingCallbackHandler` están listos para este flujo, el `EmbeddingClient` actual en `AgentExecutionService` utiliza principalmente el método `generate_embeddings_sync`. Este método implementa un patrón **pseudo-síncrono**, donde el cliente mismo espera una respuesta en una cola de Redis única (basada en un `correlation_id`) en lugar de depender de este mecanismo de callback general hacia el `ExecutionWorker`.
    *   Por lo tanto, no está claro qué componente dentro de AES estaría actualmente iniciando solicitudes de embedding asíncronas que resultarían en un `embedding.callback` procesado de esta manera.

#### 15.2. QueryService -> AgentExecutionService (Callback)

*   **Acción de Dominio**: `query.callback`
*   **Emisor Potencial**: `QueryService`
*   **Receptor**: `AgentExecutionService` (específicamente `agent_execution_service.workers.execution_worker.ExecutionWorker`, que delega a `agent_execution_service.handlers.query_callback_handler.QueryCallbackHandler`)
*   **Cola Predeterminada**: `query:callbacks` (el `ExecutionWorker` está configurado para escuchar en esta cola)
*   **Propósito Teórico**: Notificar al `AgentExecutionService` sobre la finalización (exitosa o con error) de una solicitud de consulta RAG o búsqueda de documentos que AES habría iniciado de forma asíncrona.
*   **Payload Típico (Ejemplo de `QueryCallbackAction`)**:
    ```json
    {
        "action_type": "query.callback",
        "tenant_id": "some_tenant_id",
        "task_id": "original_query_request_task_id",
        "status": "completed",
        "result": {
            "query_type": "rag",
            "response": "Respuesta generada por RAG",
            "documents": [{"id": "doc1", "content": "...", "score": 0.9}, ...],
            "processing_time": 2.5
        },
        "execution_context": { ... }
    }
    ```
*   **Mecanismo de Manejo en AES**:
    *   Similar al `EmbeddingCallbackHandler`, el `QueryCallbackHandler` está diseñado para un patrón de **espera activa**:
        1.  Almacena el resultado/error del callback asociado al `task_id`.
        2.  Notifica a una posible corrutina en espera mediante `asyncio.Event`.
        3.  Expone métodos como `wait_for_query_result(task_id, timeout)` que el iniciador de la solicitud asíncrona llamaría.
*   **Estado Actual de la Implementación**:
    *   Al igual que con los embeddings, el `QueryClient` actual en `AgentExecutionService` utiliza métodos pseudo-síncronos (`generate_rag_sync`, `search_documents_sync`) que gestionan la espera de respuestas en colas de `correlation_id` dedicadas.
    *   No está claro qué componente dentro de AES estaría actualmente iniciando solicitudes de consulta asíncronas que utilizarían este mecanismo de `query.callback`.

**Conclusión sobre Callbacks Asíncronos a AES**:
El `AgentExecutionService` posee la infraestructura para manejar callbacks asíncronos de `EmbeddingService` y `QueryService`. Sin embargo, los flujos de cliente primarios observados en AES para interactuar con estos servicios han evolucionado hacia un patrón pseudo-síncrono. La funcionalidad de callback en `ExecutionWorker` y sus handlers asociados podría ser para flexibilidad futura, usos internos específicos no cubiertos por los clientes principales, o remanentes de arquitecturas anteriores.

### 16. AgentOrchestratorService -> AgentManagementService

Esta interacción permite al `AgentOrchestratorService` obtener la configuración de un agente basándose en su URL slug, típicamente cuando un usuario final accede a un agente publicado.

*   **Acción de Dominio**: `agent.get_config_for_slug`
*   **Emisor**: `AgentOrchestratorService` (específicamente `agent_orchestrator_service.clients.management_client.ManagementClient`)
*   **Receptor**: `AgentManagementService` (específicamente `agent_management_service.workers.management_worker.ManagementWorker`)
*   **Cola Predeterminada**: `agent_management:{tenant_id}:actions` (siguiendo el patrón estándar)
*   **Propósito**: Recuperar la configuración completa de un agente (incluyendo plantilla, herramientas, modelo, etc.) utilizando el slug público del agente como identificador.
*   **Payload Típico (Ejemplo)**:
    ```json
    {
        "action_type": "agent.get_config_for_slug",
        "tenant_id": "some_tenant_id", // El tenant_id podría ser conocido o inferido
        "data": {
            "slug": "mi-agente-asombroso"
        },
        "correlation_id": "unique_correlation_id_for_response", // Para patrón pseudo-síncrono
        "response_queue": "orchestrator:responses:agent_config_slug:unique_correlation_id_for_response" // Para patrón pseudo-síncrono
    }
    ```
*   **Implementación Actual**:
    *   El `ManagementClient` en `AgentOrchestratorService` construye y envía la `DomainAction` `agent.get_config_for_slug`.
    *   El `ManagementWorker` en `AgentManagementService` tiene un handler en su método `_handle_action` que procesa esta solicitud, busca el agente por slug y devuelve su configuración.
    *   Este flujo utiliza un patrón **pseudo-síncrono**, donde el `ManagementClient` espera una respuesta en una cola de Redis específica (`response_queue`) identificada por un `correlation_id`.
*   **Notas Adicionales**:
    *   Esta es una comunicación crucial para permitir el acceso público o compartido a agentes configurados en el sistema.

---

Con esto, hemos cubierto las principales interacciones basadas en colas Redis identificadas entre los servicios. El documento `inter_service_communication.md` ahora refleja un análisis detallado de estos flujos, incluyendo funcionalidades pendientes y patrones de comunicación específicos.
