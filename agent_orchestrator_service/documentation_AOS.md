# Documentación: Agent Orchestrator Service

## 1. Objetivo Principal del Servicio

El **Agent Orchestrator Service** actúa como el principal intermediario de comunicación en tiempo real entre los clientes (interfaces de usuario, aplicaciones móviles, etc.) y el **Agent Execution Service (AES)**. Su función primordial es gestionar las interacciones de chat, facilitar la comunicación bidireccional mediante WebSockets y orquestar el flujo de mensajes y respuestas de los agentes inteligentes.

Permite a los usuarios enviar mensajes a los agentes y recibir respuestas y actualizaciones de estado de forma asíncrona y en tiempo real. Además, maneja la contextualización de las solicitudes, la autenticación básica de las conexiones WebSocket y el enrutamiento de las acciones de ejecución hacia el AES.

## 2. Mecanismos de Comunicación

El servicio utiliza varios mecanismos de comunicación:

*   **WebSockets**: Es el canal principal para la comunicación bidireccional en tiempo real con los clientes. Una vez que un cliente establece una conexión WebSocket, el servicio puede enviarle respuestas del agente, actualizaciones de estado y errores.
    *   Gestionado por `WebSocketManager` y las rutas en `routes/websocket_routes.py`.
    *   Los clientes se conectan al endpoint `/ws/{session_id}` proporcionando `tenant_id`, `tenant_tier`, `agent_id` (opcional), `user_id` (opcional) y un `token` (actualmente placeholder) como query parameters.
*   **API REST (HTTP)**:
    *   **Para Clientes**: Expone endpoints REST (principalmente en `routes/chat_routes.py`) para que los clientes inicien interacciones de chat (ej. `/api/chat/send`). Estas solicitudes son asíncronas; el servicio las acepta, las encola para procesamiento por el AES y responde inmediatamente con un `task_id`.
    *   **Interna/Health Checks**: Expone endpoints para health checks (`/health`, `/health/detailed`) y estadísticas (`/ws/stats`, `/api/chat/stats`).
*   **Colas Redis (Domain Actions)**:
    *   **Hacia Agent Execution Service (AES)**: Cuando se recibe un mensaje de chat vía API REST, el `ChatHandler` (implícito en `chat_routes.py`) crea una `ChatProcessAction` y la encola en una cola Redis específica del AES (ej. `nooble4:dev:agent_execution_service:actions:{tier}`). El `DomainQueueManager` gestiona la nomenclatura de estas colas.
    *   **Desde Agent Execution Service (AES)**: El `OrchestratorWorker` escucha colas Redis dedicadas a callbacks (ej. `orchestrator:{tenant_id}:callbacks`). El AES envía `ExecutionCallbackAction` a estas colas cuando una tarea de agente se completa o falla.

## 3. Componentes Internos Clave

*   **`main.py`**: Punto de entrada del servicio FastAPI. Inicializa la aplicación, monta las rutas y arranca el `OrchestratorWorker`.
*   **`config/settings.py`**: Define la configuración del servicio (`OrchestratorSettings`), incluyendo límites de conexión WebSocket, timeouts, y configuraciones de Redis.
*   **`workers/orchestrator_worker.py` (`OrchestratorWorker`)**: Un `BaseWorker` que escucha en colas Redis específicas (`orchestrator:{tenant_id}:callbacks`) los `ExecutionCallbackAction` enviados por el Agent Execution Service. Al recibir un callback, lo delega al `CallbackHandler` para su procesamiento.
*   **`handlers/context_handler.py` (`ContextHandler`)**: Responsable de crear y gestionar el `ExecutionContext` a partir de la información de los headers HTTP (en `chat_routes.py`) o query parameters (en `websocket_routes.py`). Este contexto es crucial para la validación, el enrutamiento por tier y la trazabilidad.
*   **`handlers/callback_handler.py` (`CallbackHandler`)**: Procesa los `ExecutionCallbackAction` recibidos por el `OrchestratorWorker`. Determina si la ejecución fue exitosa o fallida, formatea el resultado (o error) en un `WebSocketMessage` y utiliza el `WebSocketManager` para enviar este mensaje a la sesión de cliente correcta a través de la conexión WebSocket activa.
*   **`services/websocket_manager.py` (`WebSocketManager`)**: Componente central para la gestión de todas las conexiones WebSocket activas. Mantiene un registro de las conexiones por `connection_id`, `session_id`, `tenant_id` y `tenant_tier`. Proporciona métodos para conectar, desconectar, enviar mensajes a conexiones/sesiones específicas, hacer broadcast por tier/tenant, y limpiar conexiones obsoletas. Implementa un patrón singleton.
*   **`routes/websocket_routes.py`**: Define el endpoint principal `/ws/{session_id}` para establecer conexiones WebSocket. Maneja la aceptación de la conexión, la registra en el `WebSocketManager`, y gestiona el bucle de recepción/envío de mensajes WebSocket (como pings/pongs y confirmaciones).
*   **`routes/chat_routes.py`**: Define los endpoints REST para las interacciones de chat, principalmente `/api/chat/send`. Valida los headers (X-Tenant-ID, X-Agent-ID, X-Tenant-Tier, X-Session-ID), crea el `ExecutionContext` usando `ContextHandler`, construye una `ChatProcessAction` y la encola para el Agent Execution Service usando `DomainQueueManager`.
*   **`routes/health_routes.py`**: Proporciona endpoints de health check (`/health`, `/health/detailed`) para monitorear el estado del servicio y sus dependencias (como Redis y el estado de las conexiones WebSocket).
*   **`models/actions_model.py`**: Define los modelos Pydantic para las acciones específicas de este servicio, como `ChatProcessAction` (enviada al AES) y `ExecutionCallbackAction` (recibida del AES).
*   **`models/websocket_model.py`**: Define los modelos Pydantic para los mensajes WebSocket (`WebSocketMessage`, `WebSocketMessageType`) y la información de conexión (`ConnectionInfo`).

## 4. Integración y Flujo de Datos

El Agent Orchestrator Service se integra principalmente con los Clientes y el Agent Execution Service.

**Flujo Típico de un Mensaje de Chat:**

1.  **Conexión WebSocket Inicial**: El cliente establece una conexión WebSocket con `/ws/{session_id}`, proporcionando `tenant_id`, `tenant_tier`, `agent_id` (opcional), `user_id` (opcional) y `token` (opcional) como query parameters. `websocket_routes.py` maneja esto, y `WebSocketManager` registra la conexión.
2.  **Envío de Mensaje (Cliente -> Orchestrator)**: El cliente envía un nuevo mensaje de chat mediante una solicitud HTTP POST a `/api/chat/send`. La solicitud incluye el mensaje del usuario y headers (`X-Tenant-ID`, `X-Agent-ID`, `X-Tenant-Tier`, `X-Session-ID`, etc.).
3.  **Procesamiento Inicial (Orchestrator)**:
    *   `chat_routes.py` recibe la solicitud.
    *   `ContextHandler` crea un `ExecutionContext` a partir de los headers.
    *   Se genera un `task_id` único.
    *   Se define una `callback_queue` (ej. `orchestrator:{tenant_id}:callbacks`).
    *   Se crea una `ChatProcessAction` con el mensaje, el contexto, `task_id` y `callback_queue`.
4.  **Encolado para Ejecución (Orchestrator -> AES)**: La `ChatProcessAction` se encola en una cola Redis del Agent Execution Service (ej. `nooble4:dev:agent_execution_service:actions:{tier}`) usando `DomainQueueManager`.
5.  **Respuesta Inmediata (Orchestrator -> Cliente)**: El endpoint `/api/chat/send` responde inmediatamente al cliente con un HTTP 200 OK, incluyendo el `task_id` y un tiempo estimado, confirmando que el mensaje ha sido aceptado para procesamiento.
6.  **Procesamiento del Agente (AES)**: El Agent Execution Service consume la `ChatProcessAction` de su cola, ejecuta la lógica del agente correspondiente y procesa el mensaje.
7.  **Callback de Ejecución (AES -> Orchestrator)**: Una vez que el AES completa el procesamiento (con éxito o error), envía una `ExecutionCallbackAction` a la `callback_queue` especificada (ej. `orchestrator:{tenant_id}:callbacks`). Esta acción contiene el `task_id` original, el estado (`completed` o `failed`), y el resultado o error.
8.  **Procesamiento del Callback (Orchestrator)**:
    *   El `OrchestratorWorker` del Agent Orchestrator Service está escuchando en la `callback_queue`.
    *   Al recibir la `ExecutionCallbackAction`, la pasa al `CallbackHandler`.
9.  **Envío de Respuesta al Cliente (Orchestrator -> Cliente vía WebSocket)**:
    *   El `CallbackHandler` parsea la `ExecutionCallbackAction`.
    *   Formatea el resultado (o error) en un `WebSocketMessage` (tipo `AGENT_RESPONSE` o `ERROR`).
    *   Utiliza `WebSocketManager.send_to_session(session_id, ws_message)` para enviar el mensaje a través de la conexión WebSocket activa del cliente, usando el `session_id` original.
10. **Recepción de Respuesta (Cliente)**: El cliente recibe la respuesta del agente o el error a través de su conexión WebSocket.

## 5. Inconsistencias o Puntos de Mejora

*   **Validación de Token WebSocket**: La validación del token en `routes/websocket_routes.py` (`_validate_websocket_token`) es actualmente un placeholder (`return True` o chequea `debug_token`). Necesita una implementación robusta (ej. validación JWT) para asegurar las conexiones.
*   **Manejo de Sesiones Desconectadas (Store & Forward)**: En `CallbackHandler._handle_successful_execution`, hay un `TODO` para considerar un mecanismo de "store & forward" si no se puede enviar un mensaje WebSocket porque la sesión no está activa. Esto mejoraría la fiabilidad si los clientes se desconectan y reconectan.
*   **Sistema de Suscripciones WebSocket**: En `WebSocketManager._handle_subscription`, hay un `TODO` para implementar un sistema de suscripciones a eventos específicos. Esto podría permitir a los clientes suscribirse a actualizaciones más granulares.
*   **Rate Limiting WebSocket**: En `WebSocketManager._track_message_rate`, el tracking de la tasa de mensajes está implementado, pero la aplicación real de límites (ej. enviar error o desconectar si se excede) es un `TODO`.
*   **Persistencia de Conexiones WebSocket**: El estado de las conexiones WebSocket se mantiene en memoria. Para un sistema distribuido y escalable, esto podría ser un punto de fallo único o un cuello de botella. Se podría considerar una solución de backplane de Redis para compartir el estado de las conexiones entre múltiples instancias del orquestador, aunque esto añade complejidad.
*   **Métricas Detalladas**: Aunque hay tracking de performance para callbacks y estadísticas de conexión, se podrían expandir las métricas para incluir latencias de extremo a extremo, tasas de error por agente/tenant, etc.
*   **Configuración de Timeouts**: Los timeouts para las acciones (`ChatProcessAction.timeout`) se obtienen del `ExecutionContext.metadata`, que a su vez parece depender de la configuración inicial. Sería bueno asegurar que estos timeouts son configurables de manera flexible y se propagan correctamente.

## 6. Código Muerto o Duplicado

Durante la revisión actual, no se identificó código evidentemente muerto o duplicado de forma significativa. Las funcionalidades parecen estar bien encapsuladas en sus respectivos módulos.

*   La dependencia `get_context_handler_dep` en `websocket_routes.py` no parece ser utilizada directamente por el endpoint `@router.websocket("/ws/{session_id}")`, aunque sí se usa en `chat_routes.py`. El `ContextHandler` se instancia directamente en `main.py` para el worker. Esto no es código muerto, pero la dependencia podría eliminarse de `websocket_routes.py` si no se planea usarla allí.

---
*Documentación generada por Cascade AI.*
