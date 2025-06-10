# Propuesta de Estandarización de Handlers en Nooble4

## 1. Introducción

Este documento propone un modelo estandarizado para los "handlers" dentro de los servicios de Nooble4. El objetivo es alinear la implementación de la lógica de negocio con la arquitectura `BaseWorker 4.0` (específicamente su método `_handle_action`), mejorar la claridad, la testeabilidad y la organización del código que procesa las `DomainActions`.

Se revisará la jerarquía de clases propuesta por el usuario y se integrarán sus conceptos con un enfoque adaptado al `BaseWorker`.

## 2. Contexto: BaseWorker 4.0 y el Rol de `_handle_action`

Las memorias indican una refactorización hacia `BaseWorker 4.0`, que incluye un método abstracto clave: `async def _handle_action(self, action: DomainAction, context: ExecutionContext) -> Optional[DomainActionResponse]:`. 

Este método en cada worker específico (ej. `ManagementWorker`, `ConversationWorker`) es el punto de entrada para procesar una `DomainAction` recibida de una cola Redis. Por lo tanto, cualquier "handler" que definamos debe operar en conjunto o ser invocado desde este método.

## 3. Revisión de la Jerarquía de Handlers Propuesta por el Usuario

La jerarquía propuesta es:

```
BaseHandler
  |
  +-- BaseContextHandler (OrchestratorContextHandler, etc.)
  |
  +-- BaseActionHandler (WebSocketHandler, AgentExecutionHandler, etc.)
  |
  +-- BaseCallbackHandler
        |
        +-- CallbackSenderHandler (ExecutionCallbackHandler, etc.)
        +-- CallbackReceiverHandler (OrchestratorCallbackHandler, etc.)
```

**Análisis y Consideraciones:**

*   **`BaseHandler`**: Un buen punto de partida conceptual.
*   **`BaseContextHandler`**: La idea de manejar "contexto" es vital. En el paradigma `BaseWorker 4.0`, el `ExecutionContext` ya se pasa al método `_handle_action`. En lugar de una clase base separada para handlers de contexto, el contexto debe ser una dependencia o parámetro para los handlers de acciones.
*   **`BaseActionHandler`**: Este es el concepto más directamente alineado con el procesamiento de `DomainActions`. Los handlers específicos como `AgentExecutionHandler`, `QueryHandler` encajan aquí. El `WebSocketHandler` y `ChatHandler` podrían ser casos especiales si interactúan directamente con WebSockets antes de que una `DomainAction` se forme, o si procesan `DomainActions` destinadas a WebSockets.
*   **`BaseCallbackHandler`**:
    *   **`CallbackSenderHandler`**: El envío de callbacks (que son `DomainActions` dirigidas a colas de respuesta o callback específicas) es una responsabilidad del servicio que *genera* el callback. Esto se haría típicamente usando un cliente Redis (como el definido en `standart_client.md`) desde dentro de la lógica de un `BaseActionHandler` o del propio `_handle_action`. No parece necesario un tipo de "handler" separado para *enviar*.
    *   **`CallbackReceiverHandler`**: La recepción y procesamiento de callbacks es importante. Un callback entrante es simplemente una `DomainAction` en una cola específica. El `_handle_action` del worker que escucha esa cola recibirá esta `DomainAction`. Por lo tanto, el procesamiento de un callback puede ser manejado por un método dentro de un `BaseActionHandler` (ej. `QueryHandler.handle_embedding_callback(...)`).

## 4. Propuesta de Estandarización de Handlers (Alineada con BaseWorker 4.0)

Se propone una estructura donde los "Handlers" son clases que encapsulan la lógica de negocio para un conjunto de `action_types` relacionados. El `BaseWorker` instancia y delega a estos handlers.

### 4.1. `BaseActionHandler` (Clase Base Común)

*   **Ubicación**: `nooble4.common.handlers.base_action_handler.py`
*   **Propósito**: Definir la interfaz y proveer funcionalidad común para todos los handlers de acciones, incluyendo acceso a un cliente Redis para enviar respuestas o nuevas acciones (callbacks).
*   **Estructura Sugerida**:

    ```python
    # nooble4/common/handlers/base_action_handler.py
    from abc import ABC
    from typing import Any, Optional, Type
    import logging
    from pydantic import BaseModel
    # Ajustar las rutas de importación según la estructura real del proyecto
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse, ErrorDetail
    from nooble4.common.clients.redis_client import BaseRedisClient # Asumiendo que el cliente estandarizado está aquí
    from nooble4.common.utils.execution_context import ExecutionContext 

    logger = logging.getLogger(__name__)

    class BaseActionHandler(ABC):
        def __init__(self, redis_client: BaseRedisClient, settings: Optional[Any] = None, **dependencies):
            """
            Inicializa el handler.
            Args:
                redis_client: Cliente Redis (BaseRedisClient) para comunicaciones salientes.
                settings: Configuración específica del servicio.
                dependencies: Otros servicios o utilidades inyectadas (ej. logger, other_services).
            """
            self.redis_client = redis_client
            self.settings = settings
            self.logger = dependencies.get('logger', logger) # Usar logger inyectado o el logger del módulo
            for key, value in dependencies.items():
                if not hasattr(self, key):
                    setattr(self, key, value)

        def _deserialize_action_data(self, action: DomainAction, data_model: Type[BaseModel]) -> BaseModel:
            """Deserializa action.data en el modelo Pydantic esperado."""
            try:
                return data_model.model_validate(action.data)
            except Exception as e:
                self.logger.error(f"Error deserializando data para action {action.action_id} ({action.action_type}) en {data_model.__name__}: {e}")
                # Podría lanzar una excepción específica que el worker maneje para devolver un error Bad Request.
                raise ValueError(f"Invalid data payload for {action.action_type}: {e}")

        def _prepare_success_response(
            self, 
            original_action: DomainAction, 
            response_data_payload: Optional[BaseModel] = None
        ) -> DomainActionResponse:
            """Prepara una DomainActionResponse exitosa."""
            return DomainActionResponse(
                success=True,
                correlation_id=original_action.correlation_id,
                trace_id=original_action.trace_id, # Propagar trace_id
                action_type_response_to=original_action.action_type,
                data=response_data_payload.model_dump(mode='json') if response_data_payload else None
            )

        def _prepare_error_response(
            self, 
            original_action: DomainAction, 
            error_type: str, 
            message: str, 
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None
        ) -> DomainActionResponse:
            """Prepara una DomainActionResponse de error."""
            return DomainActionResponse(
                success=False,
                correlation_id=original_action.correlation_id,
                trace_id=original_action.trace_id, # Propagar trace_id
                action_type_response_to=original_action.action_type,
                error=ErrorDetail(
                    error_type=error_type,
                    message=message,
                    error_code=error_code,
                    details=details
                )
            )
    ```

### 4.2. Handlers Específicos del Servicio

*   **Herencia**: Cada handler específico (ej. `ManagementHandler`, `ConversationHandler`) hereda de `BaseActionHandler`.
*   **Ubicación**: `[nombre_servicio]/handlers/[nombre_handler].py` (ej. `agent_management_service/handlers/management_handler.py`).
*   **Responsabilidad**: Implementar métodos públicos que manejan `action_types` específicos. Cada método recibe `action: DomainAction` y `context: ExecutionContext`.
*   **Ejemplo (`ManagementHandler`)**:

    ```python
    # agent_management_service/handlers/management_handler.py
    from pydantic import BaseModel, Field
    import uuid
    from typing import Optional, Dict, Any

    from nooble4.common.handlers.base_action_handler import BaseActionHandler
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse
    from nooble4.common.utils.execution_context import ExecutionContext
    # Importar modelos Pydantic específicos para esta acción/servicio
    # Ejemplo:
    # from ..payload_models.agent_config import GetAgentConfigRequest, AgentConfigResponse

    # --- Definición de Modelos Pydantic para Payloads (ejemplos) ---
    class GetAgentConfigRequestData(BaseModel):
        agent_id: uuid.UUID

    class AgentConfigData(BaseModel):
        agent_id: uuid.UUID
        name: str
        version: str
        # ... otros campos de configuración

    class AgentConfigResponseData(BaseModel):
        config: AgentConfigData
    # --- Fin de Modelos Pydantic ---

    class ManagementHandler(BaseActionHandler):
        async def handle_get_agent_config(self, action: DomainAction, context: ExecutionContext) -> DomainActionResponse:
            try:
                request_data = self._deserialize_action_data(action, GetAgentConfigRequestData)
                self.logger.info(f"Handling get_agent_config for agent_id: {request_data.agent_id}, tenant: {action.tenant_id}")
                
                # ... lógica de negocio para obtener la configuración del agente ...
                # agent_config_from_db = await self.db_service.get_agent_config(request_data.agent_id, action.tenant_id)
                # Simulación:
                if request_data.agent_id == uuid.UUID("00000000-0000-0000-0000-000000000001"): # Ejemplo de ID encontrado
                    agent_config_data = AgentConfigData(
                        agent_id=request_data.agent_id, 
                        name="Test Agent", 
                        version="1.0"
                    )
                    response_payload = AgentConfigResponseData(config=agent_config_data)
                    return self._prepare_success_response(action, response_payload)
                else:
                    self.logger.warning(f"Agent config not found for agent_id: {request_data.agent_id}")
                    return self._prepare_error_response(action, error_type="NotFound", message="Agent configuration not found.", error_code="AGENT_NOT_FOUND")
            
            except ValueError as ve: # Error de deserialización
                 self.logger.error(f"Invalid payload for get_agent_config: {ve}")
                 return self._prepare_error_response(action, error_type="BadRequest", message=str(ve), error_code="INVALID_PAYLOAD")
            except Exception as e:
                self.logger.error(f"Error in handle_get_agent_config for action {action.action_id}: {e}", exc_info=True)
                return self._prepare_error_response(action, error_type="InternalServerError", message=f"An unexpected error occurred: {str(e)}", error_code="INTERNAL_ERROR")

        # Ejemplo de handler que necesita enviar un callback (acción asíncrona)
        async def handle_start_long_process(self, action: DomainAction, context: ExecutionContext) -> Optional[DomainActionResponse]:
            # Para una acción que es fire-and-forget desde la perspectiva del solicitante original,
            # pero que el handler luego necesita enviar un callback.
            # No se devuelve DomainActionResponse directamente al worker para el solicitante original.
            # El solicitante original debe haber usado send_action_async_with_callback.

            # request_data = self._deserialize_action_data(action, StartLongProcessRequestData)
            self.logger.info(f"Starting long process for action {action.action_id}, corr_id: {action.correlation_id}")

            # ... iniciar proceso largo ...

            # Cuando el proceso largo termina (o en un punto intermedio), enviar un callback
            if action.callback_queue_name and action.callback_action_type and self.redis_client:
                callback_data_payload = BaseModel() # Reemplazar con el modelo Pydantic del payload del callback
                # callback_data_payload = LongProcessResultData(status="completed", result_details={...})
                
                self.logger.info(f"Sending callback for action {action.action_id} to {action.callback_queue_name} with type {action.callback_action_type}")
                # El cliente Redis debe ser capaz de enviar un DomainAction completo.
                # El BaseRedisClient de standart_client.md tiene métodos para esto.
                # Aquí asumimos que el BaseRedisClient tiene un método genérico send_domain_action_async
                # o que usamos el método send_action_async pasándole todos los detalles.
                
                # Construir el DomainAction para el callback
                # El correlation_id del callback DEBE ser el correlation_id de la acción original que solicitó el callback.
                # El trace_id también se propaga.
                # El action_id del callback es nuevo.
                # El origin_service es el servicio actual (el que envía el callback).

                # Usando el método send_action_async del BaseRedisClient (adaptado para enviar a una cola específica)
                # Esto requiere que el BaseRedisClient pueda tomar un target_queue_name directamente.
                # O, mejor, el BaseRedisClient tiene un método específico para enviar callbacks.
                # Por ahora, asumimos que el handler puede usar el redis_client para construir y enviar.
                
                # Simulación de envío de callback (la lógica real estaría en self.redis_client.send_action_async o similar)
                callback_action = DomainAction(
                    action_type=action.callback_action_type,
                    data=callback_data_payload.model_dump(mode='json'),
                    origin_service=self.redis_client.origin_service_name, # El servicio que envía el callback
                    correlation_id=action.correlation_id, # CRUCIAL: el de la acción original
                    trace_id=action.trace_id, # Propagar trace_id
                    tenant_id=action.tenant_id,
                    user_id=action.user_id,
                    session_id=action.session_id
                    # No se necesita callback_queue_name ni callback_action_type en el callback mismo, a menos que sea encadenado.
                )
                try:
                    # Idealmente, el redis_client tiene un método como:
                    # await self.redis_client.send_raw_domain_action(action.callback_queue_name, callback_action)
                    # O si send_action_async puede tomar una cola destino arbitraria:
                    # await self.redis_client.send_action_async_to_queue(
                    #    target_queue=action.callback_queue_name,
                    #    domain_action_to_send=callback_action
                    # )
                    # Para este ejemplo, simulamos el rpush directo, pero debería ser a través del cliente.
                    self.redis_client.redis_conn.rpush(action.callback_queue_name, callback_action.model_dump_json())
                    self.logger.info(f"Successfully sent callback for original action {action.action_id} to {action.callback_queue_name}")
                except Exception as e:
                    self.logger.error(f"Failed to send callback for action {action.action_id} to {action.callback_queue_name}: {e}", exc_info=True)
            else:
                self.logger.warning(f"Callback not sent for action {action.action_id}: callback_queue_name or callback_action_type missing.")
            
            return None # No hay respuesta directa para el solicitante original de start_long_process
        
        # ... otros métodos para action_types de 'management.*'
    ```

### 4.3. Integración con el Worker (`_handle_action`)

El método `_handle_action` del worker específico instancia el handler (o lo recibe por inyección de dependencias) y utiliza un mapa de despacho para invocar al método correcto del handler.

*   **Ejemplo (`ManagementWorker`)**:

    ```python
    # agent_management_service/workers/management_worker.py
    import logging
    from nooble4.common.workers.base_worker import BaseWorker
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse, ErrorDetail
    from nooble4.common.utils.execution_context import ExecutionContext
    from nooble4.common.clients.redis_client import BaseRedisClient # Para instanciar y pasar al handler
    from ..handlers.management_handler import ManagementHandler # Ruta relativa al handler
    # Importar settings, etc.

    class ManagementWorker(BaseWorker):
        def __init__(self, redis_url: str, settings: Any, logger: logging.Logger, **kwargs):
            super().__init__(redis_url, settings, logger, **kwargs) # Asumiendo que BaseWorker toma redis_url
            
            # Instanciar el cliente Redis común que usará el handler para enviar callbacks u otras acciones.
            # El origin_service_name para este cliente es el nombre de este servicio (ManagementService).
            # Este cliente NO se usa para enviar la respuesta de la acción actual (eso lo hace el worker abajo).
            handler_redis_client = BaseRedisClient(
                redis_url=redis_url, 
                origin_service_name=settings.SERVICE_NAME # Suponiendo que el nombre del servicio está en settings
            )
            
            self.handler = ManagementHandler(redis_client=handler_redis_client, settings=settings, logger=logger)
            
            self.action_map = {
                "management.agent.get_config": self.handler.handle_get_agent_config,
                # "management.agent.update_config": self.handler.handle_update_agent_config,
                "management.process.start_long": self.handler.handle_start_long_process, # Ejemplo de acción que envía callback
                # ... otros action_types de este worker
            }

        async def _send_response(self, response_queue_name: str, response: DomainActionResponse):
            """Envía la DomainActionResponse a la cola de respuesta especificada."""
            if not response_queue_name:
                self.logger.warning(f"No response_queue_name provided for response to action {response.action_type_response_to} (CorrID: {response.correlation_id}). Response not sent.")
                return
            try:
                # Usar la conexión Redis del worker (self.redis_conn) para enviar la respuesta.
                # No usar el handler_redis_client para esto, ya que es una respuesta directa, no una nueva acción.
                await self.redis_conn.rpush(response_queue_name, response.model_dump_json())
                self.logger.debug(f"Sent response for {response.action_type_response_to} (CorrID: {response.correlation_id}) to {response_queue_name}")
            except Exception as e:
                self.logger.error(f"Failed to send response to {response_queue_name} for CorrID {response.correlation_id}: {e}", exc_info=True)

        async def _handle_action(self, action: DomainAction, context: ExecutionContext) -> None:
            # _handle_action ahora no devuelve DomainActionResponse directamente.
            # En su lugar, si hay una respuesta, la envía usando _send_response.
            self.logger.info(f"Processing action: {action.action_type} ({action.action_id}), CorrID: {action.correlation_id}, TraceID: {action.trace_id}")
            handler_method = self.action_map.get(action.action_type)
            response: Optional[DomainActionResponse] = None

            if handler_method:
                try:
                    # El método del handler puede devolver una DomainActionResponse (para pseudo-sync)
                    # o None (para fire-and-forget o si el handler envía su propio callback).
                    response = await handler_method(action, context)
                except ValueError as ve: # Capturar errores de validación/deserialización del handler
                    self.logger.error(f"ValueError processing action {action.action_id} ({action.action_type}): {ve}", exc_info=True)
                    response = DomainActionResponse(
                        success=False, 
                        correlation_id=action.correlation_id, 
                        trace_id=action.trace_id,
                        action_type_response_to=action.action_type,
                        error=ErrorDetail(error_type="BadRequest", message=str(ve), error_code="INVALID_PAYLOAD_HANDLER")
                    )
                except Exception as e:
                    self.logger.error(f"Unhandled error processing action {action.action_id} ({action.action_type}): {e}", exc_info=True)
                    response = DomainActionResponse(
                        success=False, 
                        correlation_id=action.correlation_id, 
                        trace_id=action.trace_id,
                        action_type_response_to=action.action_type,
                        error=ErrorDetail(error_type="InternalServerError", message=f"Internal server error: {str(e)}", error_code="HANDLER_EXCEPTION")
                    )
            else:
                self.logger.warning(f"No handler registered for action_type: {action.action_type} (ActionID: {action.action_id})")
                response = DomainActionResponse(
                    success=False, 
                    correlation_id=action.correlation_id, 
                    trace_id=action.trace_id,
                    action_type_response_to=action.action_type,
                    error=ErrorDetail(error_type="NotImplemented", message=f"Action type {action.action_type} not supported.", error_code="ACTION_NOT_SUPPORTED")
                )
            
            # Si hay una respuesta y la acción original especificó una callback_queue_name (para pseudo-sync),
            # entonces enviar la respuesta a esa cola.
            if response and action.callback_queue_name:
                await self._send_response(action.callback_queue_name, response)
            elif response:
                # Se generó una respuesta, pero no hay cola de respuesta especificada (ej. error en una acción async pura).
                # Podríamos loggearlo o enviarlo a una cola de errores generales si es necesario.
                self.logger.info(f"Generated response for action {action.action_id} (CorrID: {action.correlation_id}) but no callback_queue_name was specified. Response: {response.success}")
            # Si response es None, es una acción fire-and-forget o el handler maneja su propia comunicación (ej. callback).
    ```

### 4.4. Manejo de Callbacks

#### Envío de Callbacks (desde un Handler)

Cuando un handler completa una operación asíncrona para la cual se solicitó un callback (la `DomainAction` original contenía `callback_queue_name` y `callback_action_type`), el handler es responsable de construir y enviar una *nueva* `DomainAction` (el callback) a la cola especificada.

*   Utilizará el `self.redis_client` (una instancia de `BaseRedisClient` inyectada) para esto.
*   La nueva `DomainAction` (el callback) debe:
    *   Tener su `action_type` igual al `callback_action_type` de la `DomainAction` original.
    *   Tener su `correlation_id` igual al `correlation_id` de la `DomainAction` original (esto es crucial para que el receptor del callback pueda correlacionarlo).
    *   Propagar el `trace_id` de la `DomainAction` original.
    *   Contener los datos del resultado en su campo `data` (serializados desde un modelo Pydantic).
    *   Ser enviada a la `callback_queue_name` especificada en la `DomainAction` original.
    *   El `origin_service` del callback será el servicio actual que está enviando el callback.
*   Ver el ejemplo `handle_start_long_process` en la sección 4.2 para una ilustración.

#### Recepción de Callbacks (en un Handler)

*   Los callbacks recibidos son, en sí mismos, `DomainActions` que llegan a una cola de callbacks específica del servicio (ej. `nooble4:dev:origin_service:callbacks:some_process_result:correlation_id` o una cola más genérica como `nooble4:dev:origin_service:callbacks`).
*   El worker que escucha estas colas de callbacks procesará estas `DomainActions` a través de su método `_handle_action`.
*   Se definen métodos específicos en el handler correspondiente para estos `action_types` de callback.
    *   Ejemplo en un `OrchestrationHandler` que solicitó un embedding y ahora recibe el callback:
        ```python
        # ... (imports y modelos Pydantic para el callback de embedding) ...
        # class EmbeddingCallbackData(BaseModel):
        #     original_document_id: str
        #     embedding_vector: List[float]
        #     status: str # "success" or "failure"
        #     error_message: Optional[str]

        class OrchestrationHandler(BaseActionHandler):
            # ... otros métodos ...

            async def handle_embedding_result_callback(self, action: DomainAction, context: ExecutionContext) -> Optional[DomainActionResponse]:
                # action.action_type sería algo como "embedding.batch.generated" (el callback_action_type original)
                # action.correlation_id es el ID que el OrchestrationHandler usó cuando solicitó el embedding.
                self.logger.info(f"Received embedding callback. Original CorrID: {action.correlation_id}, TraceID: {action.trace_id}")
                
                try:
                    # callback_data = self._deserialize_action_data(action, EmbeddingCallbackData)
                    # self.logger.info(f"Embedding status for doc {callback_data.original_document_id}: {callback_data.status}")
                    
                    # Lógica para procesar el resultado del embedding:
                    # - Actualizar estado interno (ej. en una base de datos o caché de la orquestación).
                    # - Si el embedding fue exitoso, podría desencadenar la siguiente acción en el flujo (ej. llamar a un LLM).
                    # - Si falló, manejar el error (ej. reintentar, notificar).

                    # Ejemplo: si esto es parte de un flujo más grande, podría enviar otra acción.
                    # if callback_data.status == "success" and self.redis_client:
                    #     next_action_payload = ...
                    #     await self.redis_client.send_action_async(
                    #         target_service_name="LLMService", 
                    #         action_type="llm.generate.text", 
                    #         action_data_payload=next_action_payload,
                    #         tenant_id=action.tenant_id, 
                    #         # Propagar correlation_id si el flujo general está correlacionado, o generar uno nuevo.
                    #         # El trace_id siempre se propaga.
                    #         existing_trace_id=action.trace_id,
                    #         correlation_id_for_flow=action.correlation_id # O un ID de flujo superior si existe
                    #     )
                    pass # No se devuelve DomainActionResponse si este callback no responde a un pseudo-sync.
                except ValueError as ve:
                    self.logger.error(f"Invalid payload for embedding callback {action.action_id}: {ve}")
                    # Podría enviar una notificación de error a una cola de monitoreo si es necesario.
                except Exception as e:
                    self.logger.error(f"Error processing embedding callback {action.action_id}: {e}", exc_info=True)
                
                return None # Generalmente, los handlers de callback no devuelven una DomainActionResponse.
        ```
    *   El `OrchestrationWorker` añadiría el `action_type` del callback (ej. `"embedding.batch.generated"`) a su `action_map`, apuntando a `self.handler.handle_embedding_result_callback`.

### 4.5. `WebSocketHandler` y Casos Especiales

*   Si un `WebSocketHandler` (ej. en `AgentOrchestratorService`) gestiona directamente mensajes de WebSocket y *luego* crea `DomainActions` para otros servicios, su estructura podría ser diferente, ya que no consumiría `DomainActions` de Redis como entrada principal.
*   Sin embargo, si hay `DomainActions` que instruyen al servicio a enviar mensajes por WebSocket (ej. `websocket.send_message`), entonces un `WebSocketActionHandler(BaseActionHandler)` sería apropiado.

## 5. Ventajas de esta Estandarización

*   **Claridad y Organización**: Separa la lógica de orquestación del worker de la lógica de negocio del handler.
*   **Alineación con BaseWorker 4.0**: Se integra naturalmente con el método `_handle_action`.
*   **Testeabilidad**: Los handlers específicos pueden ser testeados de forma aislada inyectando dependencias mockeadas.
*   **Reusabilidad**: La `BaseActionHandler` y las utilidades comunes pueden ser compartidas.
*   **Consistencia**: Proporciona un patrón uniforme para procesar acciones en todos los servicios.

## 6. Pasos Siguientes Sugeridos

1.  **Implementar `BaseActionHandler`**: Crear la clase base en el módulo común.
2.  **Refactorizar un Worker/Handler Piloto**: Elegir un servicio (ej. `AgentManagementService`) y refactorizar su worker y crear su `ManagementHandler` siguiendo esta propuesta.
3.  **Definir Ubicación de Modelos Pydantic**: Estandarizar dónde residen los modelos Pydantic para `DomainAction`, `DomainActionResponse`, y los payloads de `data` y `error` (se abordará en `standart_payload.md`).
4.  **Evaluar y Ajustar**: Revisar la implementación piloto y ajustar las directrices.
5.  **Extender**: Aplicar gradualmente al resto de los servicios.

Este enfoque simplifica la jerarquía inicial propuesta, manteniendo sus intenciones principales y adaptándolas al flujo de trabajo existente del `BaseWorker 4.0`.
