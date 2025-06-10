# Agent Execution Service

## Introducción y Propósito del Servicio

El **Agent Execution Service** es un componente backend responsable de orquestar y gestionar el ciclo de vida de la ejecución de agentes. Recibe solicitudes para ejecutar agentes, maneja la obtención del contexto necesario (configuración del agente, historial de conversación, permisos de usuario), invoca la lógica de ejecución del agente y envía el resultado de vuelta a un servicio solicitante a través de un mecanismo de callback.

Anteriormente, este servicio utilizaba Langchain para la ejecución subyacente de los agentes. **Actualmente, la integración directa con Langchain ha sido eliminada.** La funcionalidad principal de ejecución de agentes ahora está marcada como no implementada y devolverá un error si se invoca. Cualquier futura funcionalidad de ejecución de agentes requerirá una nueva implementación o la integración de una biblioteca alternativa.

El servicio sigue manejando la comunicación asíncrona a través de colas de Redis, la validación de tiers de tenencia para límites de ejecución y la interacción con otros servicios backend para obtener datos y configuraciones.

## Características y Estado Actual

| Característica                      | Descripción                                                                    | Estado      | Notas                                                                                                |
|-------------------------------------|--------------------------------------------------------------------------------|-------------|------------------------------------------------------------------------------------------------------|
| **Recepción de Tareas**             | Procesamiento asíncrono de acciones de ejecución vía Redis                    | ✅ Operativo | Utiliza `ExecutionWorker` para escuchar `DomainAction`.                                                |
| **Orquestación de Ejecución**       | Flujo principal gestionado por `AgentExecutionHandler`                         | ✅ Operativo | Prepara el contexto y llama a `AgentExecutor`.                                                         |
| **Gestión de Contexto**             | Obtención de config. de agente, historial, permisos (`ExecutionContextHandler`) | ✅ Operativo | Interactúa con Agent Management y Conversation Service (vía colas Redis pseudo-síncronas, con caché Redis sobre resultados).                    |
| **Validación por Tier**             | Aplicación de límites (ej. iteraciones, timeout) según tier de tenant        | ✅ Operativo | Lógica en `AgentExecutor._prepare_execution_params` y `ExecutionContextHandler`.                     |
| **Ejecución de Agente (Core)**      | Lógica central que ejecuta el agente con el input del usuario                  | ⚠️ No Implementado | `AgentExecutor.execute_agent` devuelve `NotImplementedError` tras eliminación de Langchain.            |
| **Integración con Servicios (Datos)**| Comunicación con Agent Management y Conversation Service para obtener datos.   | ✅ Operativo | A través de clientes que usan colas Redis pseudo-síncronas (`AgentManagementClient`, `ConversationServiceClient`).                      |
| **Gestión de Herramientas (Config)**| Preparación de configuración de herramientas disponibles para el agente          | ✅ Operativo | `AgentExecutor._prepare_execution_params` considera herramientas según tier.                         |
| **Callbacks Asíncronos (Resultados)**| Notificación de resultados vía Redis (`ExecutionCallbackHandler`)              | ✅ Operativo | Envía `ExecutionResult` (o error) a una cola de callback especificada.                               | 
| **Métricas Básicas**                | Endpoints o logging para métricas de performance                               | ⚠️ Parcial  |                                                                                                      |
| **Caché de Configuraciones/Historial**| Optimización mediante caché Redis para configs. de agentes e historial.        | ✅ Operativo | Gestionado por `ExecutionContextHandler`.                                                              |
| **Persistencia Avanzada (PostgreSQL)**| Almacenamiento de datos de ejecución en PostgreSQL                           | ❌ Pendiente |                                                                                                      |

## Arquitectura General y Flujo de Comunicación

El Agent Execution Service opera como un consumidor de mensajes de una cola de Redis. Cuando una nueva tarea de ejecución de agente es enviada (generalmente por un servicio orquestador), el `ExecutionWorker` la recoge. Este worker delega el procesamiento al `AgentExecutionHandler`, que es el componente central que coordina los pasos necesarios para una ejecución.

### Patrón de Comunicación Interna con Otros Servicios (Pseudo-Síncrono sobre Redis)

Una característica fundamental de la comunicación entre el Agent Execution Service y otros servicios internos (`Agent Management`, `Conversation`, `Embedding` y `Query Service`) es el uso de un patrón de **comunicación pseudo-síncrona sobre colas de Redis**. Este mecanismo reemplaza las llamadas HTTP directas para las operaciones principales de solicitud/respuesta de datos o ejecución de comandos, y funciona de la siguiente manera:

1.  **Solicitud (`DomainAction` con `correlation_id`)**:
    *   Cuando el Agent Execution Service (a través de sus clientes como `AgentManagementClient`, `ConversationServiceClient`, etc.) necesita interactuar con otro servicio:
        *   Se crea un `DomainAction` que encapsula la solicitud (ej. `management.get_agent_config`, `conversation.get_history`, `embedding.generate.sync`).
        *   Se genera un `correlation_id` único para esta transacción específica y se incluye en el `DomainAction`.
        *   Este `DomainAction` se publica en una **cola de entrada general** del servicio destino (ej. `management.actions`, `conversation.actions`, `embedding.actions`, `query.actions`).

2.  **Espera Activa de Respuesta (Escucha en Cola Específica)**:
    *   Inmediatamente después de publicar la solicitud, el cliente en el Agent Execution Service comienza a **escuchar de forma bloqueante (con timeout)** en una **cola de respuesta específica**.
    *   El nombre de esta cola de respuesta se construye dinámicamente usando el `correlation_id` y una convención (ej. `management:responses:get_agent_config:<correlation_id>`, `embedding:responses:generate:<correlation_id>`). Se utiliza la operación `BLPOP` de Redis.

3.  **Procesamiento por el Servicio Destino y Envío de Respuesta**:
    *   El servicio destino consume el `DomainAction` de su cola de entrada general.
    *   Procesa la solicitud.
    *   Envía la respuesta (que puede ser un JSON con los datos solicitados o un indicador de éxito/error) directamente a la **cola de respuesta específica** indicada por el `correlation_id` que venía en la solicitud original.

4.  **Recepción de Respuesta por el Cliente Origen**:
    *   El cliente en el Agent Execution Service, que estaba bloqueado esperando en la cola de respuesta específica, recibe el mensaje.
    *   Procesa la respuesta. Si no se recibe nada dentro del timeout configurado, la operación falla.

**Implicaciones de este Patrón**:
*   **Redis como Bus de Mensajes Activo**: Para estas interacciones, Redis actúa como un bus de mensajes para un flujo de request-response, no solo como un sistema de colas para tareas en segundo plano o como una caché pasiva.
*   **Simulación de Sincronicidad**: Aunque la comunicación subyacente es asíncrona (mensajes en colas), el cliente espera la respuesta, simulando una llamada síncrona para el código que lo utiliza.
*   **Caché sobre Resultados de Redis**: La caché existente (ej. en `ExecutionContextHandler` para configuraciones de agente o historial) opera sobre los *resultados obtenidos a través de este mecanismo de Redis*, no sobre resultados de llamadas HTTP directas (ya que estas no ocurren para estas operaciones).
*   **Configuración de Colas**: Los nombres de las colas de entrada de los servicios destino (ej. `management.actions`) y el patrón para las colas de respuesta son convenciones clave para que este sistema funcione.

### Flujo de Comunicación Detallado (Considerando el Patrón Pseudo-Síncrono):

1.  **Entrada de Tarea**:
    *   Un servicio externo (ej. Orquestador) publica un `DomainAction` (tipo `execution.execute`) en una cola de Redis específica (ej. `agent.execute`). Esta acción contiene los detalles de la solicitud, incluyendo el `agent_id`, el mensaje del usuario, el `execution_context` (que puede tener `tenant_id`, `session_id`, `callback_topic`, etc.).

2.  **Procesamiento Interno y Obtención de Datos**:
    *   El `ExecutionWorker` consume la acción de la cola.
    *   El `AgentExecutionHandler` toma el control:
        *   Utiliza `ExecutionContextHandler` para:
            *   **Obtener Configuración del Agente**: A través de `AgentManagementClient`, envía un `DomainAction` a la cola del **Agent Management Service** y espera la respuesta vía Redis (pseudo-síncrono). Los resultados se cachean en Redis.
            *   **Obtener Historial de Conversación**: A través de `ConversationServiceClient`, envía un `DomainAction` a la cola del **Conversation Service** y espera la respuesta vía Redis (pseudo-síncrono). Los resultados se cachean en Redis.
            *   **Validar Permisos**: Verifica si el `tenant_tier` permite la ejecución y qué límites aplican.
    *   (Si la ejecución de agentes estuviera activa y usara herramientas que requieren datos externos, `AgentExecutor` podría usar `EmbeddingClient` o `QueryClient` para comunicarse con **Embedding Service** o **Query Service** respectivamente, usando el mismo patrón de colas Redis pseudo-síncronas).

3.  **Intento de Ejecución del Agente**:
    *   `AgentExecutionHandler` invoca a `AgentExecutor.execute_agent()`.
    *   **Actualmente**: Este método devuelve inmediatamente un `ExecutionResult` con estado `FAILED` y error `NotImplementedError`.

4.  **Persistencia de Mensajes Post-Ejecución**:
    *   `AgentExecutionHandler`, a través de `ExecutionContextHandler`, llama al `ConversationServiceClient` para enviar los nuevos mensajes (input del usuario y la respuesta/error del agente) al **Conversation Service** para su persistencia. Esto invalida la caché de historial para esa sesión.

5.  **Envío de Callback (Resultado)**:
    *   `AgentExecutionHandler` utiliza `ExecutionCallbackHandler` para enviar el resultado.
    *   `ExecutionCallbackHandler` construye un `ExecutionCallbackAction` (otro tipo de `DomainAction`) que encapsula el `ExecutionResult` (o el error).
    *   Este `ExecutionCallbackAction` se publica en la cola de Redis especificada en el `callback_topic` de la solicitud original (ej. `orchestrator.execution_results`), usando `DomainQueueManager`. El servicio solicitante (Orquestador) está escuchando esta cola para recibir la respuesta final.

### Comunicación Entrante desde el Servicio Orquestador

El Agent Execution Service (AES) se activa al recibir un mensaje en una cola de Redis específica, típicamente denominada `agent.execute`. Este mensaje es un `DomainAction` enviado por un servicio solicitante, comúnmente el **Servicio Orquestador**.

La estructura del `DomainAction` que el AES espera en la cola `agent.execute` es la siguiente:

```json
{
  "action_id": "string (UUID único para esta acción específica, ej: f47ac10b-58cc-4372-a567-0e02b2c3d479)",
  "action_type": "execution.execute",
  "correlation_id": "string (UUID para correlacionar esta solicitud a través de múltiples saltos si es necesario, ej: client-generated-uuid-123)",
  "task_id": "string (UUID que identifica la tarea general o el flujo de trabajo del que forma parte esta ejecución, ej: workflow-uuid-abc)",
  "timestamp": "string (ISO 8601 datetime, ej: 2023-10-27T10:30:00Z)",
  "source_service": "string (Nombre del servicio que origina la acción, ej: orchestrator-service)",
  "payload": {
    "agent_id": "string (ID del agente a ejecutar)",
    "user_input": "string (El input o prompt del usuario para el agente)",
    "session_id": "string (Opcional, ID de la sesión de conversación)",
    "tenant_id": "string (ID del tenant/cliente)",
    "user_id": "string (ID del usuario)",
    "callback_topic": "string (Nombre de la cola Redis donde el AES debe enviar el resultado/callback, ej: orchestrator_results_queue)",
    "execution_parameters": {
      // Parámetros adicionales específicos para la ejecución
      "max_tokens": "integer (Opcional)",
      "temperature": "float (Opcional)"
    },
    "metadata": {
      // Metadatos adicionales
      "request_ip": "string (Opcional)"
    }
  }
}
```

**Campos Clave en el Payload para `execution.execute`**:

*   `agent_id`: Esencial para que el AES sepa qué configuración de agente cargar.
*   `user_input`: El prompt o la consulta que el agente debe procesar.
*   `session_id`: Utilizado para recuperar y guardar el historial de la conversación.
*   `tenant_id`, `user_id`: Para validación de permisos, aplicación de límites de tier y auditoría.
*   `callback_topic`: Crucial. Indica al AES a qué cola de Redis debe enviar el `ExecutionResult` (o error) una vez que la ejecución del agente haya finalizado o fallado. El Servicio Orquestador estará escuchando en esta cola.

El `ExecutionWorker` dentro del AES consume este `DomainAction` de la cola `agent.execute` y lo pasa al `AgentExecutionHandler` para iniciar el procesamiento.

### Diagrama Simplificado de Flujo de Comunicación

```plaintext
[Servicio Orquestador]
  │
  │ 1. Publica `execution.execute` DA (con callback_topic)
  ▼
[ Redis Queue: "agent.execute" ]
  │
  │ 2. AES: ExecutionWorker consume
  ▼
┌────────────────────────────────── Agent Execution Service (AES) ─────────────────────────────────┐
│                                                                                                  │
│  [ExecutionWorker] ─── Pasa DA ───▶ [AgentExecutionHandler]                                      │
│                                          │ Gestiona flujo general                               │
│                                          │                                                      │
│          ┌───────────────────────────────┼───────────────────────────────────┐                  │
│          │                               │                                   │                  │
│          ▼                               ▼                                   ▼                  │
│  [ExecutionContextHandler]       [AgentExecutor]             [ExecutionCallbackHandler]         │
│    │ (Obtiene contexto vía Redis)  (Actualmente No-Op)         │ Publica `execution.callback`  │
│    │                                (Potencial para Herramientas)│ DA a `callback_topic`         │
│    │                                                            │                               │
│    │ 3a. Sol: `management.get_agent_config`                     │                               │
│    ▼      (a Agent Management Svc vía "management.actions")      │                               │
│  [Redis]                                                         │                               │
│    ▲      Resp: Config Agente (vía "mngmt:resp:<cid>")           │                               │
│    │                                                             │                               │
│    │ 3b. Sol: `conversation.get_history`                        │                               │
│    ▼      (a Conversation Svc vía "conversation.actions")        │                               │
│  [Redis]                                                         │                               │
│    ▲      Resp: Historial (vía "conv:resp:<cid>")                │                               │
│    │                                                             │                               │
│    │ 3c. (Post-Ejec) Sol: `conversation.save_message`           │                               │
│    ▼      (a Conversation Svc vía "conversation.actions")        │                               │
│  [Redis]                                                         │                               │
│    ▲      Resp: Confirmación (vía "conv:resp:<cid>")             │                               │
│                                                                  │                               │
└──────────────────────────────────────────────────────────────────┴───────────────────────────────┘
                                                                     │
                                                                     │ 4. Publica `execution.callback` DA
                                                                     ▼
                                                          [ Redis Queue: callback_topic (del DA original) ]
                                                                     │
                                                                     │ 5. Orquestador consume resultado
                                                                     ▼
                                                               [Servicio Orquestador]
```

Nota sobre el diagrama: Este diagrama simplificado ilustra el flujo principal de un `DomainAction` (DA) desde el Servicio Orquestador, su procesamiento dentro del Agent Execution Service (AES), las interacciones clave con otros servicios vía Redis para obtener contexto, y el envío del resultado final. Las colas de respuesta específicas (`<servicio>:responses:<acción>:<correlation_id>`) son utilizadas por los clientes internos del AES para esperar respuestas de forma pseudo-síncrona.

### Detalle de Payloads en Colas Redis

A continuación, se describen los `DomainActions` y los payloads intercambiados por el Agent Execution Service (AES) con otros servicios a través de Redis.

#### 1. Cola de Entrada Principal: `agent.execute`

*   **Consumidor en AES**: `ExecutionWorker`
*   **Productor**: Servicio Orquestador (u otro servicio solicitante)
*   **`DomainAction` Enviado**:
    *   `action_type`: `execution.execute`
    *   `payload`: Ver la sección "Comunicación Entrante desde el Servicio Orquestador" para la estructura detallada del payload.

#### 2. Interacción con Agent Management Service

*   **Cliente en AES**: `AgentManagementClient`
*   **Cola de Solicitud**: `management.actions`
*   **`DomainAction` Enviado por AES (Ej: para obtener configuración del agente)**:
    *   `action_type`: `management.get_agent_config`
    *   `correlation_id`: `cid_cfg` (generado por `AgentManagementClient`)
    *   `payload`:
        ```json
        {
          "agent_id": "string (ID del agente cuya configuración se solicita)"
        }
        ```
*   **Cola de Respuesta Esperada**: `management:responses:get_agent_config:<cid_cfg>`
*   **Respuesta Recibida por AES (Contenido del BLPOP, no necesariamente un DomainAction completo)**:
    *   Directamente el objeto JSON de la configuración del agente o un objeto de respuesta que lo encapsula. Por ejemplo:
        ```json
        {
          "agent_id": "string",
          "name": "string",
          "description": "string",
          "tools": ["tool1", "tool2"],
          "llm_config": { ... },
          // ... otros campos de configuración
        }
        ```
    *   O, si el servicio responde con un DomainAction:
        *   `action_type`: `management.get_agent_config.response`
        *   `correlation_id`: `cid_cfg` (el mismo que la solicitud)
        *   `payload`: Contendría la configuración del agente o un error.

#### 3. Interacción con Conversation Service

*   **Cliente en AES**: `ConversationServiceClient`
*   **Cola de Solicitud**: `conversation.actions`

*   **A. Para Obtener Historial de Conversación:**
    *   **`DomainAction` Enviado por AES**:
        *   `action_type`: `conversation.get_history`
        *   `correlation_id`: `cid_hist` (generado por `ConversationServiceClient`)
        *   `payload`:
            ```json
            {
              "session_id": "string (ID de la sesión para la cual se solicita el historial)",
              "limit": "integer (Opcional, número de mensajes a recuperar)"
            }
            ```
    *   **Cola de Respuesta Esperada**: `conversation:responses:get_history:<cid_hist>`
    *   **Respuesta Recibida por AES (Contenido del BLPOP)**:
        *   Un array de objetos de mensaje. Por ejemplo:
            ```json
            [
              { "role": "user", "content": "Hola", "timestamp": "..." },
              { "role": "assistant", "content": "Hola, ¿cómo puedo ayudarte?", "timestamp": "..." }
            ]
            ```
        *   O, si el servicio responde con un DomainAction:
            *   `action_type`: `conversation.get_history.response`
            *   `correlation_id`: `cid_hist`
            *   `payload`: Contendría la lista de mensajes o un error.

*   **B. Para Guardar Mensajes de Conversación:**
    *   **`DomainAction` Enviado por AES**:
        *   `action_type`: `conversation.save_message` (o `conversation.save_messages` si es un lote)
        *   `correlation_id`: `cid_save` (generado por `ConversationServiceClient`)
        *   `payload`:
            ```json
            {
              "session_id": "string",
              "messages": [
                { "role": "user", "content": "Input del usuario...", "timestamp": "..." },
                { "role": "assistant", "content": "Respuesta del agente...", "timestamp": "..." }
              ]
            }
            ```
    *   **Cola de Respuesta Esperada**: `conversation:responses:save_message:<cid_save>`
    *   **Respuesta Recibida por AES (Contenido del BLPOP)**:
        *   Generalmente una confirmación de éxito o un error.
            ```json
            { "status": "success", "message_ids": ["id1", "id2"] }
            ```
        *   O, si el servicio responde con un DomainAction:
            *   `action_type`: `conversation.save_message.response`
            *   `correlation_id`: `cid_save`
            *   `payload`: Contendría el estado del guardado.

#### 4. Interacción con Embedding Service (Potencial, si AgentExecutor está activo)

*   **Cliente en AES**: `EmbeddingClient`
*   **Cola de Solicitud**: `embedding.actions`
*   **`DomainAction` Enviado por AES**:
    *   `action_type`: `embedding.generate.sync` (o similar)
    *   `correlation_id`: `cid_emb`
    *   `payload`:
        ```json
        {
          "texts": ["texto 1", "texto 2"],
          "model_id": "string (Opcional, ID del modelo de embedding)"
        }
        ```
*   **Cola de Respuesta Esperada**: `embedding:responses:generate_sync:<cid_emb>` (o patrón similar)
*   **Respuesta Recibida por AES**:
    *   Una lista de embeddings o un objeto que los contiene.

#### 5. Interacción con Query Service (Potencial, si AgentExecutor está activo)

*   **Cliente en AES**: `QueryClient`
*   **Cola de Solicitud**: `query.actions`
*   **`DomainAction` Enviado por AES**:
    *   `action_type`: `query.rag.sync` (o similar)
    *   `correlation_id`: `cid_qry`
    *   `payload`:
        ```json
        {
          "query_text": "string (La pregunta para RAG)",
          "vector_db_collection": "string (Nombre de la colección a consultar)",
          "top_k": "integer (Opcional)"
        }
        ```
*   **Cola de Respuesta Esperada**: `query:responses:rag_sync:<cid_qry>` (o patrón similar)
*   **Respuesta Recibida por AES**:
    *   Resultados de la consulta RAG.

#### 6. Cola de Callback de Salida

*   **Productor en AES**: `ExecutionCallbackHandler`
*   **Cola de Destino**: Especificada por `callback_topic` en la solicitud original (ej. `orchestrator_results_queue`)
*   **Consumidor**: Servicio Orquestador (u otro servicio solicitante)
*   **`DomainAction` Enviado por AES**:
    *   `action_type`: `execution.callback`
    *   `correlation_id`: `cid_orch` (el mismo `correlation_id` de la solicitud `execution.execute` original)
    *   `task_id`: `tid_orch` (el mismo `task_id` de la solicitud original)
    *   `payload`:
        ```json
        {
          "status": "string (SUCCESS, FAILED, PENDING_HUMAN_INPUT, etc.)",
          "result": {
            // Contenido del resultado, depende del agente y la ejecución
            "output_text": "string (Respuesta del agente)",
            "tool_calls": [ ... ], // Si hubo llamadas a herramientas
            // ... otros datos de resultado
          },
          "error": { // Presente si status es FAILED
            "code": "string (Código de error, ej: AGENT_EXECUTION_FAILED)",
            "message": "string (Descripción del error)",
            "details": { ... } // Detalles adicionales del error
          },
          "execution_metadata": {
            "start_time": "string (ISO 8601)",
            "end_time": "string (ISO 8601)",
            "duration_ms": "integer"
            // ... otras métricas de ejecución
          }
        }
        ```
    *   Nota: La estructura exacta de `result` y `error` dentro del payload del callback puede variar según la implementación específica del `ExecutionResult` y los tipos de error.
## Estructura de Archivos y Carpetas (Reconfirmada)

```plaintext
agent_execution_service/
├ __init__.py
├ main.py                 # Punto de entrada, inicializa el worker
├ requirements.txt        # Dependencias del servicio
├ clients/                # Clientes HTTP para otros servicios
│  ├ __init__.py
│  ├ agent_management_client.py
│  ├ conversation_client.py
│  ├ embedding_client.py   # Cliente para servicio de embeddings (para herramientas futuras)
│  └ query_client.py       # Cliente para servicio de query (para herramientas futuras)
├ config/                 # Configuración del servicio
│  ├ __init__.py
│  └ settings.py
├ handlers/               # Lógica de orquestación y manejo de contexto/callbacks
│  ├ __init__.py
│  ├ agent_execution_handler.py
│  ├ context_handler.py  # Renombrado de execution_context_handler.py
│  └ execution_callback_handler.py
├ models/                 # Modelos Pydantic para datos
│  ├ __init__.py
│  ├ actions_model.py      # Define AgentExecutionAction, ExecutionCallbackAction etc.
│  └ execution_model.py    # Define ExecutionResult, ExecutionStatus, etc.
├ services/               # Lógica de negocio central
│  ├ __init__.py
│  └ agent_executor.py     # Contiene la lógica (actualmente deshabilitada) para ejecutar un agente
└ workers/                # Workers que escuchan colas de mensajes
   ├ __init__.py
   └ execution_worker.py
```

## Descripción de Componentes Clave (Interacción con Servicios)

*   **`ExecutionWorker` (`workers/execution_worker.py`)**:
    *   Entrada: Consume `DomainAction` (tipo `execution.execute`) de una cola Redis.
    *   Salida: Delega a `AgentExecutionHandler`.

*   **`AgentExecutionHandler` (`handlers/agent_execution_handler.py`)**:
    *   Orquesta el flujo.
    *   Entrada: Recibe `AgentExecutionAction` del worker.
    *   Interacciones:
        *   Usa `ExecutionContextHandler` para obtener datos.
        *   Usa `AgentExecutor` para (intentar) ejecutar.
        *   Usa `ExecutionCallbackHandler` para enviar el resultado final.
    *   Salida: El resultado se envía vía callback.

*   **`ExecutionContextHandler` (`handlers/context_handler.py`)**:
    *   Encargado de construir y validar el `ExecutionContext`.
    *   Interacciones Salientes (vía Clientes con Patrón Pseudo-Síncrono Redis):
        *   **Agent Management Service**: Utiliza `AgentManagementClient` para enviar un `DomainAction` (ej. `management.get_agent_config`) a la cola de Agent Management y esperar la respuesta en una cola Redis específica. Los resultados (`agent_config`) se cachean en Redis por este handler.
        *   **Conversation Service**:
            *   Para obtener historial: Utiliza `ConversationServiceClient` para enviar `DomainAction` (ej. `conversation.get_history`) y esperar respuesta. Resultados (`conversation_history`) cacheados en Redis por este handler.
            *   Para guardar mensajes: Utiliza `ConversationServiceClient` para enviar `DomainAction` (ej. `conversation.save_message`) y esperar confirmación. Invalida la caché de historial relevante.
    *   Salida: Provee `agent_config`, `conversation_history` y `ExecutionContext` validado al `AgentExecutionHandler`.

*   **`AgentExecutor` (`services/agent_executor.py`)**:
    *   **Estado Actual**: No realiza comunicaciones externas ya que `execute_agent()` devuelve `NotImplementedError`.
    *   **Potencial (si se reimplementa con soporte para herramientas)**: Podría utilizar `EmbeddingClient` y `QueryClient` para interactuar con **Embedding Service** y **Query Service** respectivamente. Estas interacciones seguirían el patrón pseudo-síncrono sobre Redis:
        *   Enviarían `DomainActions` (ej. `embedding.generate.sync`, `query.rag.sync`) a las colas de los servicios correspondientes.
        *   Esperarían las respuestas en colas Redis específicas identificadas por `correlation_id`.
        *   La lógica de caché para los resultados de estas operaciones (embeddings, resultados RAG) no está implementada en los clientes actuales y necesitaría ser manejada por el `AgentExecutor` o una capa superior si se requiere.

*   **`ExecutionCallbackHandler` (`handlers/execution_callback_handler.py`)**:
    *   Entrada: Recibe el `ExecutionResult` (o detalles del error) del `AgentExecutionHandler`, junto con `task_id`, `callback_queue`, etc.
    *   Interacciones Salientes (Redis):
        *   Publica un `ExecutionCallbackAction` (un `DomainAction`) en la `callback_queue` especificada, usando `DomainQueueManager`.
    *   Salida: El resultado de la ejecución es enviado asíncronamente al servicio solicitante.

*   **`Clients` (`clients/`)**:
    *   `AgentManagementClient`, `ConversationServiceClient`, `EmbeddingClient`, `QueryClient`: Todos estos clientes implementan un patrón de comunicación **pseudo-síncrona sobre colas de Redis** para interactuar con sus respectivos servicios. Envían `DomainActions` a colas de servicio generales y esperan respuestas en colas específicas usando un `correlation_id`. **No realizan llamadas HTTP directas** para las operaciones principales documentadas (obtener configuración, historial, guardar mensajes, generar embeddings, realizar consultas RAG).

## Modelos de Datos Principales (Relevantes para Comunicación)

*   **`AgentExecutionAction` (`models/actions_model.py`)**: Define la estructura de la solicitud de ejecución recibida. Incluye `callback_topic`.
*   **`ExecutionResult` (`models/execution_model.py`)**: Define la estructura del resultado de la ejecución.
*   **`ExecutionCallbackAction` (`models/actions_model.py`)**: Define la estructura del mensaje de callback que se envía por Redis, conteniendo el `ExecutionResult` o un error.

## Configuración

La configuración del servicio se gestiona principalmente a través de variables de entorno y se carga mediante `config/settings.py`.

Principales variables de entorno (ejemplos):

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL`: Configuración para la conexión a Redis, fundamental para las colas de `DomainAction` (entrada/salida/callbacks) y el patrón de comunicación pseudo-síncrono, además de la caché.
- `AGENT_MANAGEMENT_SERVICE_URL`, `CONVERSATION_SERVICE_URL`, `EMBEDDING_SERVICE_URL`, `QUERY_SERVICE_URL`: Aunque los clientes internos para las operaciones principales ahora usan el patrón pseudo-síncrono sobre Redis, estas URLs pueden ser mantenidas por compatibilidad, para endpoints secundarios no cubiertos por el patrón de colas, o para futuras necesidades. La comunicación central para la ejecución de agentes descrita aquí se basa en Redis.
- **Nombres de Colas de Redis**: Aunque no son variables de entorno directas, los nombres de las colas son configuraciones implícitas cruciales. Ejemplos:
    - Colas de entrada de servicios: `agent.execute` (para este servicio), `management.actions`, `conversation.actions`, `embedding.actions`, `query.actions`.
    - Patrón de colas de respuesta para pseudo-síncrono: `<nombre_servicio>:responses:<nombre_metodo>:<correlation_id>`.
    - Colas de callback: Definidas por `callback_topic` en la `DomainAction` original.
- `LOG_LEVEL`: Nivel de logging (ej. `INFO`, `DEBUG`).
- `AGENT_CONFIG_CACHE_TTL_SECONDS`: TTL para la caché de configuración de agentes.
- `CONVERSATION_CACHE_TTL_SECONDS`: TTL para la caché de historial de conversación.
- `DEFAULT_CONVERSATION_CACHE_LIMIT`: Límite de mensajes en caché para historial.

## Dependencias Clave

- `fastapi`: Framework web para posibles endpoints (aunque el servicio es principalmente un worker).
- `pydantic`: Para validación de modelos de datos.
- `redis`: Cliente asíncrono para Redis (comunicación vía colas y caché).
- `httpx`: Cliente HTTP asíncrono para comunicación con otros servicios.
- `common`: Módulo compartido del proyecto con modelos y utilidades comunes (ej. `DomainAction`, `ExecutionContext`, `DomainQueueManager`).

(Las dependencias de Langchain como `langchain`, `langchain-community`, `langchain-core` han sido eliminadas o comentadas ya que la integración directa fue removida.)

## Consideraciones Actuales y Próximos Pasos

- **Reimplementación de Ejecución de Agentes**: La principal tarea pendiente es diseñar e implementar una nueva lógica para `AgentExecutor.execute_agent()` que no dependa de Langchain o que integre una alternativa de manera controlada.
- **Manejo de Herramientas (Tools)**: Si la nueva lógica de ejecución soporta herramientas que dependen de `Embedding Service` o `Query Service`, la comunicación se realizará mediante el patrón **pseudo-síncrono sobre Redis** utilizando `EmbeddingClient` y `QueryClient`. Se deberá asegurar que este flujo esté correctamente implementado, probado y documentado, incluyendo el manejo de timeouts, errores, y la estrategia de caché (ej. Redis) para las respuestas si es necesario (actualmente no implementada en los clientes).
- **Métricas Avanzadas**: Expandir el sistema de métricas para ofrecer una visión más detallada del rendimiento, tasas de error, tiempos de ejecución por agente/tier, etc.
- **Persistencia en PostgreSQL**: Evaluar y, si es necesario, implementar la persistencia de datos relevantes de ejecución (ej. logs de auditoría, resultados resumidos) en una base de datos PostgreSQL, en lugar de depender únicamente de Redis para datos volátiles.
- **Seguridad**: Asegurar que toda la comunicación entre servicios (HTTP y Redis) sea segura, utilizando TLS/SSL y mecanismos de autenticación/autorización robustos.

## Ejemplo de Domain Actions (Revisado)

### Acción de Entrada (Solicitud de Ejecución)

```json
// Publicado en una cola como agent.execute.{tenant_tier}
{
  "action_id": "unique-action-uuid-123",
  "action_type": "execution.execute", // Indica al ExecutionWorker que es una tarea de ejecución
  "task_id": "original-task-uuid-abc", // ID de la tarea/conversación original
  "tenant_id": "my-tenant-id",
  "tenant_tier": "professional", // Usado para DomainQueueManager y validación de límites
  "timestamp": "2023-10-27T10:30:00Z",
  "data": { // Payload específico de AgentExecutionAction
    "agent_id": "agent-金融分析师-007",
    "input_message": {
      "role": "user",
      "content": "¿Cuál es la previsión de ingresos para Q4?"
    },
    "session_id": "session-user123-conv456",
    "execution_context_data": { // Datos para construir el ExecutionContext
        "user_id": "user-123",
        "trace_id": "trace-xyz-789",
        // Otros datos relevantes para el contexto
    },
    "callback_topic": "orchestrator.results.professional" // Cola donde se enviará el resultado
  }
}
```

### Acción de Salida (Callback con Resultado)

```json
// Publicado en la callback_topic especificada en la acción de entrada
{
  "action_id": "unique-callback-uuid-456",
  "action_type": "execution.callback", // Tipo de acción para el consumidor del callback
  "task_id": "original-task-uuid-abc", // Mismo task_id que la solicitud original
  "tenant_id": "my-tenant-id",
  "tenant_tier": "professional",
  "timestamp": "2023-10-27T10:30:05Z",
  "data": { // Payload específico de ExecutionCallbackAction
    "execution_result": {
        "status": "COMPLETED", // o "FAILED", "TIMEOUT"
        "response": {
            "role": "assistant",
            "content": "La previsión de ingresos para Q4 es de $1.2M."
        },
        "sources": [],
        "tool_calls": [],
        "error_details": null, // o { "type": "NotImplementedError", "message": "..." }
        "iterations_used": 1,
        "max_iterations": 5,
        "started_at": "2023-10-27T10:30:01Z",
        "completed_at": "2023-10-27T10:30:04Z",
        "tokens_used": null // o { "input": 50, "output": 25, "total": 75 }
    },
    "original_request_data": { // Opcional: para referencia del consumidor
        "agent_id": "agent-金融分析师-007"
    }
  }
}
```

- **Persistencia Temporal**: Al igual que otros servicios, utiliza Redis para almacenar métricas y datos de estado. Se planea migrar a PostgreSQL para persistencia permanente.

- **Sistema de Caché**: El caché de configuraciones de agentes está implementado parcialmente y requiere optimización.

{{ ... }}

- **Configuración de Tier Enterprise**: Las capacidades del tier Enterprise para ejecutar agentes avanzados no están completamente implementadas.

### Próximos Pasos

1. **Implementar Persistencia**: Migrar métricas y datos de ejecución a PostgreSQL para almacenamiento permanente.

2. **Optimizar Caché**: Mejorar el sistema de caché para configuraciones de agentes y resultados frecuentes.

3. **Expandir Métricas**: Añadir métricas detalladas de uso, tiempos de ejecución y éxito de tareas con dashboard.

4. **Herramientas Avanzadas**: Implementar más herramientas nativas para agentes del tier Enterprise.

5. **Integración con Frontend**: Mejorar la experiencia con el frontend para visualizar el progreso de ejecución.

6. **Documentación Avanzada**: Expandir la documentación de uso con ejemplos concretos.
