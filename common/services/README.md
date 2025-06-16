# Common Services (`common.services`)

Este módulo define la capa de servicio base para los microservicios dentro del sistema Nooble4.

## `BaseService`

`BaseService` (`base_service.py`) es una clase base abstracta que establece el contrato para todas las clases de servicio específicas del dominio. Su propósito principal es orquestar la lógica de negocio de un servicio.

### Características Clave:

1.  **Punto de Entrada Único:**
    *   Define un método abstracto `async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]`.
    *   Este método es invocado por `BaseWorker` cuando se recibe una `DomainAction` destinada a este servicio.
    *   Debe ser implementado por cada servicio específico para manejar las diferentes `action.action_type` que le correspondan.
    *   El diccionario devuelto por `process_action` contiene los datos para la `DomainActionResponse` (en comunicación pseudo-síncrona) o para una `DomainAction` de callback. Si no se requiere respuesta/callback, puede devolver `None`.

2.  **Constructor y Dependencias:**
    *   Se inicializa con:
        *   `app_settings: CommonAppSettings`: La configuración común de la aplicación, que incluye `service_name`.
        *   `service_redis_client: Optional[BaseRedisClient] = None`: Una instancia opcional de `BaseRedisClient`. Se proporciona si el servicio necesita iniciar *nuevas* `DomainAction`s hacia otros servicios (no solo responder a la acción actual).
        *   `direct_redis_conn: Optional[AIORedis] = None`: Una conexión Redis asíncrona directa opcional, para operaciones que no son el envío de `DomainAction`s (por ejemplo, contadores, locks simples, gestión de estado con `RedisStateManager`).
    *   Automáticamente configura `self.service_name` y un `self._logger` contextualizado.

3.  **Orquestación de Lógica:**
    *   Dentro de `process_action`, el servicio puede:
        *   Validar los datos de la `DomainAction`.
        *   Utilizar `Handlers` (clases de utilidad de `common.handlers` o handlers específicos del servicio) para encapsular lógica de dominio compleja o interacciones con sistemas externos.
        *   Interactuar con bases de datos u otros almacenes de datos (posiblemente usando `direct_redis_conn` o `RedisStateManager`).
        *   Si se le proporcionó un `service_redis_client`, puede enviar nuevas `DomainAction`s a otros servicios.
        *   Construir y devolver el diccionario de datos para la respuesta o callback.

### Ejemplo de Implementación (en un servicio específico):

```python
# my_feature_service/services/feature_service.py
from typing import Optional, Dict, Any

from common.services import BaseService
from common.models.actions import DomainAction
# from ..handlers.my_feature_handler import MyFeatureHandler # Ejemplo de handler específico

class FeatureService(BaseService):
    # def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
    #     super().__init__(app_settings, service_redis_client, direct_redis_conn)
    #     # self.my_feature_handler = MyFeatureHandler(app_settings) # Inicializar handlers si es necesario

    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        self._logger.info(f"Procesando acción: {action.action_type} ({action.action_id})")

        if action.action_type == "feature.do_something":
            # Validar action.data si es necesario (usando modelos Pydantic)
            # input_data = MyFeatureActionPayload(**action.data)
            
            # Lógica de negocio...
            # result = await self.my_feature_handler.perform_task(input_data.some_field)
            result = {"status": "completed", "detail": f"Tarea para {action.data.get('item_id')} finalizada"}
            
            # Devolver datos para la DomainActionResponse o callback
            return result
        
        elif action.action_type == "feature.another_action":
            # ... otra lógica ...
            return {"message": "Otra acción procesada"}
        
        else:
            self._logger.warning(f"Tipo de acción no reconocido: {action.action_type}")
            # Opcionalmente, devolver un error o dejar que BaseWorker maneje la no respuesta
            return {"error": "action_type_not_supported", "message": f"Acción {action.action_type} no soportada."}

        return None # Por defecto, si ninguna condición se cumple
```

## Validación de Payloads (`action.data`) y Manejo de Metadatos (`action.metadata`)

Una responsabilidad crucial del `BaseService` (y sus implementaciones específicas) es la validación y el manejo adecuado del payload (`action.data`) y los metadatos (`action.metadata`) de la `DomainAction` entrante.

### Validación de `action.data`

1.  **Responsabilidad del Servicio:** El `action.data` llega como un diccionario (`Dict[str, Any]`). El servicio que procesa la acción es responsable de:
    *   Identificar el modelo Pydantic específico que corresponde al `action.action_type` recibido.
    *   Intentar parsear y validar el diccionario `action.data` contra este modelo Pydantic específico. Por ejemplo:
        ```python
        # Dentro de process_action en un servicio específico
        if action.action_type == "my_service.do_task":
            try:
                payload = MyTaskPayloadModel(**action.data)
            except ValidationError as e:
                self._logger.error(f"Error de validación para {action.action_type}: {e}")
                # Idealmente, levantar una excepción personalizada que BaseWorker pueda manejar
                # para enviar una DomainActionResponse de error.
                # Ejemplo: raise DataValidationError(details=e.errors())
                return {"error": "ValidationError", "message": str(e), "details": e.errors()}
        ```

2.  **Manejo de Errores de Validación:**
    *   Si la validación con Pydantic falla (se levanta una `pydantic.ValidationError`), el servicio debe manejar este error.
    *   La estrategia recomendada es levantar una excepción personalizada (ej. `DataValidationError` que herede de `MessageProcessingError` definido en `common.errors.exceptions`) que contenga los detalles del error de validación.
    *   `BaseWorker` está diseñado para capturar estas excepciones (si heredan de una base común) y construir una `DomainActionResponse` con `success=False` y los detalles del error, que luego se envía de vuelta si se proporcionó un `callback_queue_name`.
    *   Si no se maneja explícitamente y se devuelve un diccionario de error, `BaseWorker` también puede usarlo para la respuesta.

3.  **Ubicación de Modelos Pydantic:**
    *   Cada servicio debe definir sus propios modelos Pydantic para los payloads de las acciones que maneja. Estos modelos pueden residir en un subdirectorio `models/` o `schemas/` dentro del directorio del servicio específico.

### Uso de `action.data` vs. `action.metadata`

La `DomainAction` proporciona dos campos para transportar información: `data` y `metadata`.

*   **`action.data: Dict[str, Any]`**: 
    *   **Propósito**: Contiene el **payload primario y esencial** para la ejecución de la acción. Su estructura es específica para cada `action_type` y **debe ser validada** por el servicio receptor contra un modelo Pydantic dedicado, como se describió anteriormente.
    *   **Ejemplo**: Para una acción `user.create`, `action.data` contendría `{"username": "john.doe", "email": "john.doe@example.com"}`.

*   **`action.metadata: Optional[Dict[str, Any]]`**: 
    *   **Propósito**: Contiene **información auxiliar, opcional o de configuración** que puede influir en cómo se procesa la acción, pero no es parte del payload fundamental. Puede usarse para pasar parámetros como la selección de un modelo de IA específico para una tarea, flags de características para una solicitud particular, o información de contexto para logging avanzado.
    *   **Valores Predeterminados del Servicio**: Los servicios deben estar diseñados para operar con sus propios valores predeterminados para cualquier configuración que `action.metadata` pueda anular. Si `action.metadata` no se proporciona, o si una clave específica dentro de `metadata` está ausente, el servicio debe recurrir a su configuración predeterminada.
    *   **Validación**: La validación de `action.metadata` es generalmente menos estricta que la de `action.data`. El servicio puede optar por leer valores específicos de `metadata` según sea necesario, aplicando lógica de validación ad-hoc o simplemente ignorando claves desconocidas.
    *   **Ejemplo**: Para una acción `query.generate_answer`, `action.data` podría tener `{"query_text": "What is AI?"}`, mientras que `action.metadata` podría ser `{"llm_model": "gpt-4-turbo", "temperature": 0.5}`. Si `metadata` no especifica `llm_model`, el servicio de consulta usaría su modelo LLM predeterminado.

Esta distinción ayuda a mantener los payloads principales (`data`) limpios y estrictamente validados, mientras ofrece flexibilidad para pasar información contextual o de configuración (`metadata`) sin romper la compatibilidad si los servicios no la esperan o no la entienden.

## Responsabilidades del Servicio Específico

*   Implementar `process_action` para manejar todos los `action_type` relevantes.
*   Definir y utilizar `Handlers` si la lógica se vuelve compleja.
*   Gestionar su propio estado y persistencia según sea necesario.
*   Si necesita iniciar nuevas comunicaciones, asegurarse de que se le inyecte un `service_redis_client` y utilizarlo adecuadamente.
