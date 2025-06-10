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
*   **Propósito**: Definir la interfaz y proveer funcionalidad común para todos los handlers de acciones.
*   **Estructura Sugerida**:

    ```python
    # nooble4/common/handlers/base_action_handler.py
    from abc import ABC, abstractmethod
    from typing import Any, Optional
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse # Suponiendo ubicación
    from nooble4.common.clients.base_redis_client import BaseRedisClient # Suponiendo ubicación
    from nooble4.common.utils.execution_context import ExecutionContext # Suponiendo ubicación

    class BaseActionHandler(ABC):
        def __init__(self, redis_client: Optional[BaseRedisClient] = None, settings: Optional[Any] = None, **kwargs):
            """
            Inicializa el handler.
            Args:
                redis_client: Cliente Redis para posibles comunicaciones salientes (ej. enviar callbacks).
                settings: Configuración específica del servicio.
                kwargs: Otros servicios o utilidades que el handler pueda necesitar.
            """
            self.redis_client = redis_client
            self.settings = settings
            # Almacenar otros kwargs si son comunes, ej. self.logger
            for key, value in kwargs.items():
                setattr(self, key, value)

        # No es estrictamente necesario un método 'process' abstracto si el worker usa un mapa de despacho.
        # Pero podría ser útil para forzar la implementación de la lógica principal.
        # @abstractmethod
        # async def process_action(self, action: DomainAction, context: ExecutionContext) -> DomainActionResponse:
        #     pass
    ```

### 4.2. Handlers Específicos del Servicio

*   **Herencia**: Cada handler específico (ej. `ManagementHandler`, `ConversationHandler`) hereda de `BaseActionHandler`.
*   **Ubicación**: `[nombre_servicio]/handlers/[nombre_handler].py` (ej. `agent_management_service/handlers/management_handler.py`).
*   **Responsabilidad**: Implementar métodos públicos que manejan `action_types` específicos. Cada método recibe `action: DomainAction` y `context: ExecutionContext`.
*   **Ejemplo (`ManagementHandler`)**:

    ```python
    # agent_management_service/handlers/management_handler.py
    from nooble4.common.handlers.base_action_handler import BaseActionHandler
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse # Suponiendo
    from nooble4.common.utils.execution_context import ExecutionContext # Suponiendo
    # Importar modelos Pydantic para payloads, errores, etc.

    class ManagementHandler(BaseActionHandler):
        async def handle_get_agent_config(self, action: DomainAction, context: ExecutionContext) -> DomainActionResponse:
            # Lógica para obtener la configuración del agente
            # Acceder a action.data para los parámetros de solicitud
            # Usar self.settings, self.redis_client (si es necesario para llamar a otro servicio, menos común aquí)
            # o cualquier otra dependencia inyectada en __init__.
            agent_id = action.data.get("agent_id")
            tenant_id = action.tenant_id # o context.tenant_id si se estandariza así

            # ... lógica de negocio ...

            if success:
                response_data = { "agent_config": { /* ... */ } }
                return DomainActionResponse(success=True, data=response_data, correlation_id=action.correlation_id)
            else:
                # Crear respuesta de error estandarizada (ver standart_payload.md)
                return DomainActionResponse(success=False, error={ "code": "NOT_FOUND", "message": "Agent not found" }, correlation_id=action.correlation_id)

        async def handle_update_agent_config(self, action: DomainAction, context: ExecutionContext) -> DomainActionResponse:
            # Lógica similar para actualizar configuración
            pass
        
        # ... otros métodos para action_types de 'management.*'
    ```

### 4.3. Integración con el Worker (`_handle_action`)

El método `_handle_action` del worker específico instancia el handler (o lo recibe por inyección de dependencias) y utiliza un mapa de despacho para invocar al método correcto del handler.

*   **Ejemplo (`ManagementWorker`)**:

    ```python
    # agent_management_service/workers/management_worker.py
    from nooble4.common.workers.base_worker import BaseWorker
    from nooble4.common.messaging.domain_actions import DomainAction, DomainActionResponse
    from nooble4.common.utils.execution_context import ExecutionContext
    from ..handlers.management_handler import ManagementHandler # Ruta relativa al handler
    # Importar cliente Redis, settings, logger

    class ManagementWorker(BaseWorker):
        def __init__(self, redis_manager, settings, logger, **kwargs):
            super().__init__(redis_manager, settings, logger, **kwargs)
            # Idealmente, el cliente Redis se configura e instancia una vez y se pasa.
            # Esto es un ejemplo simplificado.
            # common_redis_client = BaseRedisClient(settings.redis_config) 
            self.handler = ManagementHandler(redis_client=self.redis_manager.get_client(), settings=settings, logger=logger)
            
            self.action_map = {
                "management.get_agent_config": self.handler.handle_get_agent_config,
                "management.update_agent_config": self.handler.handle_update_agent_config,
                # ... otros action_types de este worker
            }

        async def _handle_action(self, action: DomainAction, context: ExecutionContext) -> Optional[DomainActionResponse]:
            self.logger.info(f"Processing action: {action.action_type} ({action.action_id})")
            handler_method = self.action_map.get(action.action_type)

            if handler_method:
                try:
                    return await handler_method(action, context)
                except Exception as e:
                    self.logger.error(f"Error processing action {action.action_id}: {e}", exc_info=True)
                    # Crear respuesta de error genérica y estandarizada
                    return DomainActionResponse(
                        success=False, 
                        error={ "code": "INTERNAL_SERVER_ERROR", "message": str(e) }, 
                        correlation_id=action.correlation_id
                    )
            else:
                self.logger.warning(f"No handler registered for action_type: {action.action_type}")
                return DomainActionResponse(
                    success=False, 
                    error={ "code": "NOT_IMPLEMENTED", "message": f"Action type {action.action_type} not supported." }, 
                    correlation_id=action.correlation_id
                )
    ```

### 4.4. Manejo de Callbacks (Recepción)

*   Los callbacks recibidos son `DomainActions` en colas específicas (ej. `query:callbacks:{tenant_id}:{session_id}`).
*   El worker que escucha estas colas (ej. `ExecutionWorker`, `OrchestratorWorker`) las procesará a través de su `_handle_action`.
*   Se pueden definir métodos específicos en el handler correspondiente para estos callbacks.
    *   Ejemplo en `ExecutionHandler` (para `agent_execution_service`):
        ```python
        class ExecutionHandler(BaseActionHandler):
            # ... otros métodos ...
            async def handle_query_callback(self, action: DomainAction, context: ExecutionContext) -> Optional[DomainActionResponse]:
                # Lógica para procesar el resultado de una búsqueda RAG que llega como callback
                # action.data contendrá los resultados de QS
                # Puede que no devuelva una DomainActionResponse si solo actualiza estado interno
                # o si luego desencadena otra acción (ej. llamar al LLM).
                pass
        ```
    *   El `ExecutionWorker` añadiría `"query.callback": self.handler.handle_query_callback` a su `action_map`.

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
