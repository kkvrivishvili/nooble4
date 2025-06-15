# Estándar: Capa de Servicio y Componentes de Negocio

## 1. Introducción: La Capa de Servicio Moderna

La arquitectura v4.1 refina la **Capa de Servicio** (`Service Layer`) como el **núcleo de la lógica de negocio** de un microservicio. Se aleja del patrón de múltiples handlers registrados para adoptar un enfoque más cohesivo y orientado a objetos.

- **Contrato Centralizado:** Toda clase de servicio **debe** heredar de `common.services.BaseService`. Esta clase base proporciona:
    - Inicialización estándar (configuración, logger).
    - Acceso a un `BaseRedisClient` (`self.service_redis_client`) para la comunicación entre servicios.
    - Acceso a una conexión directa de `AIORedis` (`self.direct_redis_conn`) para operaciones directas con Redis (por ejemplo, para `RedisStateManager`).
    - Un método abstracto `async def process_action(self, action: DomainAction)` que actúa como el **único punto de entrada** para todas las acciones que el servicio puede manejar.

El antiguo patrón de `register_handler("action.type", handler_func)` está **OBSOLETO**.

## 2. La Capa de Servicio (`Service Layer`)

Una clase de servicio (ej: `QueryProcessingService` en `query_service`) es una clase Python que encapsula y orquesta procesos de negocio. Es el principal colaborador del `Worker`.

**Responsabilidades Clave:**

- **Procesar `DomainAction`s**: Implementa el método `async def process_action(self, action: DomainAction)`. El `Worker` invoca este método para cada `DomainAction` recibida.
- **Orquestar el Flujo de Trabajo**: Dentro de `process_action`, el servicio determina el tipo de acción y dirige el flujo, que puede incluir validación, procesamiento, persistencia de estado, y comunicación con otros servicios.
- **Delegar a Componentes de Utilidad**: Utiliza componentes más pequeños y enfocados para tareas específicas (ver sección 3).
- **Gestionar Comunicación y Estado**: Utiliza `self.service_redis_client` (una instancia de `BaseRedisClient`) para enviar acciones, respuestas o callbacks a otros servicios. Utiliza `self.direct_redis_conn` (una instancia de `AIORedis`), a menudo a través de un `RedisStateManager`, para gestionar el estado en Redis.
- **Manejo de Errores**: Implementa un manejo de errores robusto y puede utilizar `self.service_redis_client` para enviar respuestas de error estandarizadas.

### Ejemplo: `ExampleProcessingService`

```python
# example_service/services/example_processing_service.py

from typing import Optional
from redis.asyncio import Redis as AIORedis

from common.services.base_service import BaseService
from common.config.base_settings import CommonAppSettings
from common.clients.base_redis_client import BaseRedisClient
from common.clients.redis_state_manager import RedisStateManager
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail
from common.models.example_models import ( # Supongamos que existen estos modelos
    ProcessDataActionPayload,
    ProcessDataResponsePayload,
    UpdateStatusActionPayload
)

# Componentes de utilidad (ejemplos)
class DataValidator:
    async def validate(self, data: dict) -> bool:
        # Lógica de validación...
        self._logger.info("Data validated successfully.")
        return True

class DataProcessor:
    async def process(self, data: dict) -> dict:
        # Lógica de procesamiento...
        self._logger.info("Data processed successfully.")
        return {"processed_field": "processed_value"}

class ExampleProcessingService(BaseService):
    """
    Servicio de ejemplo que procesa diferentes tipos de acciones.
    """

    def __init__(self,
                 app_settings: CommonAppSettings,
                 service_redis_client: Optional[BaseRedisClient] = None,
                 direct_redis_conn: Optional[AIORedis] = None):
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # Inicializar componentes de utilidad
        self.validator = DataValidator()
        self.processor = DataProcessor()
        # RedisStateManager para gestionar estado si es necesario
        self.state_manager = RedisStateManager(app_settings, self.direct_redis_conn, "example_service_state")
        self._logger.info(f"{self.service_name} initialized with client {self.service_redis_client} and conn {self.direct_redis_conn}")

    async def process_action(self, action: DomainAction):
        """
        Punto de entrada único para todas las acciones dirigidas a este servicio.
        """
        self._logger.info(f"Processing action: {action.action_id}, type: {action.action_type}")

        try:
            if action.action_type == "example.process_data":
                payload = ProcessDataActionPayload(**action.data)
                await self._handle_process_data(action, payload)
            elif action.action_type == "example.update_status":
                payload = UpdateStatusActionPayload(**action.data)
                await self._handle_update_status(action, payload)
            else:
                self._logger.warning(f"Unknown action type: {action.action_type}")
                # Opcionalmente, enviar una respuesta de error si es un patrón pseudo-síncrono
                if action.callback_queue_name:
                    error_response = DomainActionResponse(
                        success=False,
                        correlation_id=action.correlation_id,
                        trace_id=action.trace_id,
                        action_type_response_to=action.action_type,
                        error=ErrorDetail(error_code="UNKNOWN_ACTION_TYPE", message=f"Action type {action.action_type} not supported.")
                    )
                    await self.service_redis_client.send_response(action.callback_queue_name, error_response)
        except Exception as e:
            self._logger.error(f"Error processing action {action.action_id}: {e}", exc_info=True)
            if action.callback_queue_name: # Enviar error si se espera respuesta
                error_response = DomainActionResponse(
                    success=False,
                    correlation_id=action.correlation_id,
                    trace_id=action.trace_id,
                    action_type_response_to=action.action_type,
                    error=ErrorDetail(error_code="PROCESSING_ERROR", message=str(e))
                )
                await self.service_redis_client.send_response(action.callback_queue_name, error_response)

    async def _handle_process_data(self, original_action: DomainAction, payload: ProcessDataActionPayload):
        self._logger.info(f"Handling process_data for {original_action.action_id}")
        # 1. Validar
        if not await self.validator.validate(payload.data_to_process):
            # Enviar respuesta de error si es pseudo-síncrono
            if original_action.callback_queue_name:
                response = DomainActionResponse(
                    success=False, correlation_id=original_action.correlation_id, trace_id=original_action.trace_id,
                    action_type_response_to=original_action.action_type,
                    error=ErrorDetail(error_code="VALIDATION_ERROR", message="Invalid data")
                )
                await self.service_redis_client.send_response(original_action.callback_queue_name, response)
            return

        # 2. Procesar
        processed_data = await self.processor.process(payload.data_to_process)
        
        # 3. Guardar estado (ejemplo)
        await self.state_manager.set_state(f"item:{payload.item_id}:status", "processed")

        # 4. Enviar respuesta (si es pseudo-síncrono)
        if original_action.callback_queue_name:
            response_payload = ProcessDataResponsePayload(item_id=payload.item_id, result=processed_data)
            response = DomainActionResponse(
                success=True, correlation_id=original_action.correlation_id, trace_id=original_action.trace_id,
                action_type_response_to=original_action.action_type, data=response_payload.model_dump()
            )
            await self.service_redis_client.send_response(original_action.callback_queue_name, response)
        
        # 5. Opcional: Enviar una acción de callback asíncrona
        if original_action.callback_action_type and original_action.callback_queue_name_for_async_callback:
            callback_action_payload = UpdateStatusActionPayload(item_id=payload.item_id, new_status="processing_complete")
            await self.service_redis_client.send_action_async_with_callback(
                target_queue_name=original_action.callback_queue_name_for_async_callback, # Esto debería ser el callback_queue_name original
                action_type=original_action.callback_action_type,
                data=callback_action_payload,
                origin_service=self.service_name, # El servicio actual es el origen del callback
                correlation_id=original_action.correlation_id, # Propagar IDs
                trace_id=original_action.trace_id
            )
        self._logger.info(f"Finished handling process_data for {original_action.action_id}")

    async def _handle_update_status(self, original_action: DomainAction, payload: UpdateStatusActionPayload):
        self._logger.info(f"Handling update_status for item {payload.item_id} to {payload.new_status}")
        await self.state_manager.set_state(f"item:{payload.item_id}:status", payload.new_status)
        # Esta acción podría ser fire-and-forget, sin respuesta directa.
        self._logger.info(f"Finished handling update_status for {original_action.action_id}")

```

## 3. Componentes de Utilidad de Dominio

La Capa de Servicio delega tareas específicas a otras clases o componentes más pequeños. Estos siguen el **Principio de Responsabilidad Única** y son instanciados y utilizados por el servicio.

**Tipos Comunes de Componentes de Utilidad:**

- **Processors** (ej: `DataProcessor` en el ejemplo anterior): Clases que realizan el "trabajo pesado" o el núcleo de la lógica algorítmica. Pueden interactuar con sistemas externos (modelos de IA, APIs de terceros) si es necesario, aunque idealmente las interacciones externas directas se manejan a través de clientes dedicados.
- **Validators** (ej: `DataValidator`): Se especializan en validar datos de entrada, permisos o reglas de negocio complejas.
- **Otros Componentes Específicos del Dominio**: Cualquier otra clase que encapsule una pieza reutilizable de lógica de negocio (ej: calculadoras, transformadores de datos, etc.).

**Componentes de Infraestructura Utilizados por el Servicio:**

- **`common.clients.RedisStateManager`**: Utilizado para la persistencia y recuperación de estado relacionado con las operaciones del servicio (ej: contexto de una conversación, estado de una tarea). El servicio lo instancia con `app_settings` y `self.direct_redis_conn`.
- **`common.clients.BaseRedisClient`**: `self.service_redis_client` es una instancia de esta clase, proporcionada a `BaseService`. Se utiliza para toda la comunicación entre servicios (enviar acciones, respuestas, callbacks) a través de Redis Streams/Queues.

## 4. Interacción y Flujo

El flujo completo es el siguiente:

`Redis Stream/Queue` -> `Worker` -> `Service Layer (process_action)` -> `(Componentes de Utilidad, RedisStateManager, BaseRedisClient)` -> `Redis Stream/Queue (para otros servicios)`

1.  Una `DomainAction` llega a un Stream/Queue de Redis que el **Worker** está escuchando.
2.  El **Worker** consume la `DomainAction`.
3.  El **Worker** invoca el método `process_action(action)` de la instancia de **Servicio** configurada.
4.  Dentro de `process_action`, la **Capa de Servicio**:
    a.  Determina el tipo de acción y la lógica de negocio específica.
    b.  Utiliza **Componentes de Utilidad** (Processors, Validators) para tareas específicas.
    c.  Interactúa con **`RedisStateManager`** (usando `self.direct_redis_conn`) para leer o escribir estado si es necesario.
    d.  Utiliza **`self.service_redis_client`** (`BaseRedisClient`) para:
        i.  Enviar `DomainActionResponse` si la acción original era parte de un flujo pseudo-síncrono (tenía `callback_queue_name`).
        ii. Enviar nuevas `DomainAction` a otros servicios (fire-and-forget o con expectativa de callback).
        iii.Enviar `DomainAction` de callback si la acción original lo especificaba (`callback_action_type` y `callback_queue_name_for_async_callback`).
5.  El método `process_action` completa su ejecución. El `Worker` generalmente no espera un valor de retorno directo de `process_action` que necesite procesar; la comunicación de resultados/errores se maneja por el servicio a través de `BaseRedisClient`.
6.  El `Worker` confirma (ACK) el mensaje original de Redis si `process_action` se completó sin excepciones no controladas (o según la lógica de reintentos del worker).

---
Fecha de Revisión: 2025-06-15
