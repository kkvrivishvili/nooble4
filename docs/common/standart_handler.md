# Estándar: Componentes de Utilidad de Dominio (`BaseHandler` y Clases de Apoyo)

> **Última Revisión:** 15 de Junio de 2025
> **Estado:** Implementado y Activo.
> **Clase Base de Referencia:** `common.handlers.base_handler.BaseHandler`

## 1. El Rol de los "Handlers" (Componentes de Utilidad) en la Nueva Arquitectura

Con la introducción de `common.services.BaseService` como el orquestador central de la lógica de negocio, el concepto de "Handler" se ha simplificado enormemente. Ya no son clases cargadas dinámicamente para procesar acciones específicas, ni existen múltiples clases base complejas para diferentes tipos de handlers (como `BaseContextHandler` o `BaseCallbackHandler`, que han sido eliminados o refactorizados).

Ahora, un "Handler" (o más precisamente, un **Componente de Utilidad de Dominio**) es típicamente una clase que:

1.  **Hereda de `common.handlers.BaseHandler`**: Esta clase base es ahora muy mínima. Su principal propósito es:
    *   Inicializar un `self._logger` contextualizado con el nombre del servicio y el nombre de la clase del handler.
    *   Proporcionar acceso a `self.app_settings` (una instancia de `CommonAppSettings`).
2.  **Encapsula Lógica Específica**: Contiene métodos que realizan tareas de negocio concretas y bien definidas que el `BaseService` puede delegar.
3.  **Es Instanciada y Usada Explícitamente**: La capa de `Service` crea instancias de estos componentes de utilidad cuando los necesita y llama a sus métodos directamente.

**Principios Clave:**

-   **Simplicidad**: Los componentes de utilidad deben ser lo más simples posible.
-   **Responsabilidad Única**: Cada componente (o método dentro de él) se enfoca en una tarea específica (ej: realizar un cálculo complejo, interactuar con una API externa específica, transformar datos de una manera particular).
-   **Desacoplamiento del Worker**: No tienen conocimiento del `Worker` ni de la `DomainAction` cruda, a menos que el `Service` les pase datos específicos de ella.
-   **Sin Gestión de Estado Compleja Inherente**: `BaseHandler` no gestiona estado. Si un componente necesita persistir o recuperar estado, el `Service` debería proporcionarle una instancia de `RedisStateManager` o una conexión Redis directa.

## 2. El Flujo de Trabajo

El flujo de procesamiento de una acción sigue siendo claro:

1.  El **`Worker`** (`BaseWorker`) recibe una `DomainAction` desde un Redis Stream.
2.  El `Worker` deserializa la acción y llama a `self.service.process_action(action)` (asumiendo que el worker tiene una instancia de un `BaseService`).
3.  La **`Capa de Servicio`** (`BaseService` y sus subclases) es la orquestadora. Su método `process_action` (o métodos internos llamados por este) contiene la lógica de alto nivel para manejar la acción.
4.  Para implementar la lógica, el `Service` puede:
    *   Realizar el trabajo directamente.
    *   Instanciar y utilizar uno o más **Componentes de Utilidad** (que heredan de `BaseHandler`) para delegar tareas específicas.
    *   Utilizar clientes como `BaseRedisClient` (para enviar más acciones) o `RedisStateManager` (para gestionar estado).

```mermaid
graph TD
    A[Worker (BaseWorker)] -- Recibe DomainAction --> B(Delega a Servicio);
    B -- Llama a service.process_action() --> C[Servicio (BaseService)];
    C -- Orquesta lógica --> D{Puede usar:};
    D -- 1. Lógica directa --> C;
    D -- 2. --> E[Componente de Utilidad (hereda de BaseHandler)];
    E -- Realiza tarea específica --> C;
    D -- 3. --> F[BaseRedisClient];
    F -- Envía nueva acción --> C;
    D -- 4. --> G[RedisStateManager];
    G -- Carga/Guarda Estado --> C;
```

## 3. Ejemplos de Componentes de Utilidad

Ya no existen `BaseContextHandler` ni `BaseCallbackHandler` como clases base separadas en `common.handlers`.

*   **Gestión de Estado/Contexto**: Si un servicio necesita cargar/guardar datos relacionados con el contexto de una acción (ej: estado de sesión, configuración de tenant), debe usar `common.clients.RedisStateManager`. El `Service` instanciaría `RedisStateManager` y lo usaría directamente o lo pasaría a un componente de utilidad si la lógica de manipulación de ese estado es compleja.

*   **Envío de Callbacks**: Si un servicio necesita enviar una `DomainAction` como callback, lo hará directamente usando su instancia de `BaseRedisClient` (o un cliente específico de servicio que herede de él).

*   **Otros Componentes de Utilidad**: Para cualquier otra lógica de negocio que se quiera encapsular fuera del método principal del `Service`:

    ```python
    # En my_service/handlers/calculation_handler.py
    from common.handlers import BaseHandler
    from common.config import CommonAppSettings
    from redis.asyncio import Redis as AIORedis

    class CalculationHandler(BaseHandler):
        def __init__(self, app_settings: CommonAppSettings, direct_redis_conn: Optional[AIORedis] = None):
            super().__init__(app_settings, direct_redis_conn) # direct_redis_conn es opcional en BaseHandler
            # Si este handler necesita una conexión Redis específica, el Service debe proveerla.
            self.specific_config_value = app_settings.some_service_specific_setting # Ejemplo

        async def perform_complex_calculation(self, input_data: dict) -> float:
            self._logger.info(f"Performing calculation with {input_data} and {self.specific_config_value}")
            # ... lógica de cálculo ...
            result = sum(input_data.values()) * (self.specific_config_value or 1)
            return float(result)

    # Uso en el Service:
    # class MyService(BaseService):
    #     async def __init__(self, app_settings, service_redis_client, direct_redis_conn):
    #         super().__init__(app_settings, service_redis_client, direct_redis_conn)
    #         self.calc_handler = CalculationHandler(app_settings, direct_redis_conn) # O solo app_settings
    #
    #     async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
    #         if action.action_type == "my_service.do_calculation":
    #             # ... validaciones, etc. ...
    #             calculation_result = await self.calc_handler.perform_complex_calculation(action.data)
    #             return {"result": calculation_result}
    #         # ...
    ```

## 4. Conclusión

La arquitectura actual promueve un `BaseService` fuerte que orquesta la lógica de negocio. Los "Handlers" son ahora **Componentes de Utilidad** simples y opcionales que heredan de un `BaseHandler` mínimo, principalmente para obtener un logger configurado y acceso a `app_settings`.

Este enfoque simplifica la estructura del código, reduce la sobrecarga de clases base innecesarias y mantiene la lógica de negocio centralizada y explícita dentro de la capa de Servicio, que puede delegar tareas específicas a estos componentes de utilidad cuando sea apropiado.
