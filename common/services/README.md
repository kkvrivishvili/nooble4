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

## Responsabilidades del Servicio Específico

*   Implementar `process_action` para manejar todos los `action_type` relevantes.
*   Definir y utilizar `Handlers` si la lógica se vuelve compleja.
*   Gestionar su propio estado y persistencia según sea necesario.
*   Si necesita iniciar nuevas comunicaciones, asegurarse de que se le inyecte un `service_redis_client` y utilizarlo adecuadamente.
