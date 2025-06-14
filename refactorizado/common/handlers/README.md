# Módulo de Handlers Comunes (`refactorizado.common.handlers`)

## Visión General

Este módulo proporciona un conjunto de clases base abstractas diseñadas para estandarizar y simplificar la creación de handlers dentro de los diversos servicios de la aplicación Nooble4. Los handlers son componentes responsables de procesar unidades de trabajo específicas, como acciones de dominio, callbacks o interacciones que requieren la gestión de un estado (contexto).

Al heredar de estas clases base, los desarrolladores pueden centrarse en la lógica de negocio específica de su handler, mientras que la infraestructura común (logging, inicialización, validación de datos, gestión de callbacks, persistencia de contexto) es gestionada por las clases base.

## Clases Base Proporcionadas

El módulo exporta las siguientes clases base a través de `refactorizado.common.handlers.__init__`:

1.  **`BaseHandler(ABC)`**
    *   **Propósito:** Es la clase raíz abstracta para todos los handlers del sistema.
    *   **Características Clave:**
        *   Proporciona un logger configurado (`self._logger`) con el nombre del servicio y la clase del handler.
        *   Implementa un patrón para la inicialización asíncrona explícita y segura para concurrencia (`async initialize()`, `async _async_init()`). Las subclases pueden sobrescribir `_async_init()` para la lógica de inicialización que requiera `await`.
        *   Define un método abstracto `async execute()` que debe ser implementado por las subclases. Este es el punto de entrada principal que los workers llamarán para ejecutar la lógica del handler.

2.  **`BaseActionHandler(BaseHandler)`**
    *   **Propósito:** Especializada para handlers que procesan una `DomainAction` específica.
    *   **Características Clave:**
        *   Requiere una instancia de `DomainAction` y `RedisPool` en su constructor.
        *   Utiliza modelos Pydantic opcionales (`action_data_model` y `response_data_model`) para validar automáticamente el `action.data` de la `DomainAction` entrante y el objeto de respuesta devuelto por el handler, respectivamente.
        *   El método `execute()` orquesta la validación de `action.data` y luego llama al método abstracto `async handle(self, validated_data: Optional[Any]) -> Optional[BaseModel]`, que las subclases deben implementar para la lógica de negocio.

3.  **`BaseCallbackHandler(BaseActionHandler)`**
    *   **Propósito:** Extiende `BaseActionHandler` para simplificar el envío de `DomainAction` de callback como parte del procesamiento de una acción.
    *   **Características Clave:**
        *   Proporciona un método protegido `async _send_callback(self, callback_data: BaseModel, ...)` que construye y envía una nueva `DomainAction` (el callback) a la cola especificada en la acción original (o una sobrescrita).
        *   Propaga automáticamente identificadores importantes como `correlation_id`, `task_id`, y `trace_id` a la acción de callback.
        *   **Nota Importante:** Actualmente utiliza el `RedisPool` de forma síncrona, lo cual es incompatible con el `RedisPool` asíncrono principal. Ver `inconsistencies.md`.

4.  **`BaseContextHandler(BaseActionHandler)`**
    *   **Propósito:** Extiende `BaseActionHandler` para gestionar un "contexto" (un objeto de estado) persistido en Redis durante el procesamiento de una `DomainAction`.
    *   **Características Clave:**
        *   Orquesta un ciclo de "leer-modificar-guardar" para un objeto de contexto (definido por `context_model: Type[BaseModel]`) antes y después de ejecutar la lógica de negocio.
        *   Requiere que las subclases implementen `async get_context_key(self) -> str` para definir la clave de Redis para el contexto.
        *   El método `execute()` carga el contexto, valida la acción, llama al método abstracto `async handle(self, context: Optional[BaseModel], validated_data: Optional[Any]) -> Tuple[Optional[BaseModel], Optional[BaseModel]]`. Este `handle` debe devolver el contexto actualizado y el objeto de respuesta.
        *   El contexto actualizado se guarda (o elimina si es `None`) en Redis.
        *   **Nota Importante:** Al igual que `BaseCallbackHandler`, actualmente utiliza el `RedisPool` de forma síncrona. Ver `inconsistencies.md`.

## Uso

Para utilizar estos handlers, se debe crear una nueva clase que herede de la clase base más apropiada e implemente sus métodos abstractos.

**Ejemplo (Subclase de `BaseActionHandler`):**

```python
from pydantic import BaseModel
from typing import Optional

from refactorizado.common.handlers import BaseActionHandler
from refactorizado.common.models.actions import DomainAction
from refactorizado.common.redis_pool import RedisPool # Asumiendo RedisPool disponible

class MiAccionData(BaseModel):
    parametro_uno: str
    parametro_dos: int

class MiRespuestaData(BaseModel):
    resultado: str

class MiHandlerDeAccion(BaseActionHandler):
    action_data_model = MiAccionData
    response_data_model = MiRespuestaData

    def __init__(self, action: DomainAction, redis_pool: RedisPool, service_name: str, mi_dependencia_extra: Any):
        super().__init__(action=action, redis_pool=redis_pool, service_name=service_name)
        self.mi_dependencia_extra = mi_dependencia_extra # Ejemplo de dependencia adicional

    async def _async_init(self) -> None:
        # Lógica de inicialización asíncrona si es necesaria
        self._logger.info(f"Inicializando MiHandlerDeAccion para la acción {self.action.action_id}")
        await super()._async_init() # Buena práctica llamar al del padre

    async def handle(self, validated_data: MiAccionData) -> Optional[MiRespuestaData]:
        self._logger.info(f"Procesando acción {self.action.action_type} con datos: {validated_data}")
        
        # Lógica de negocio aquí...
        resultado_procesamiento = f"{validated_data.parametro_uno} - {validated_data.parametro_dos * 2}"
        
        # Devolver instancia del response_data_model o None
        return MiRespuestaData(resultado=resultado_procesamiento)

```

## Inconsistencias y Puntos a Considerar

Existen algunas inconsistencias y puntos importantes a tener en cuenta al utilizar este módulo, particularmente en relación con el uso de `RedisPool`:

*   **Importación de `RedisPool`:** Asegúrese de que la ruta de importación para `RedisPool` sea la correcta (`from refactorizado.common.redis_pool import RedisPool`).
*   **Incompatibilidad Síncrono/Asíncrono (CRÍTICO):** `BaseCallbackHandler` y `BaseContextHandler` actualmente interactúan con `RedisPool` de manera síncrona. Esto es incompatible con la implementación principal de `RedisPool` en `refactorizado.common.redis_pool`, que es asíncrona. Esta es una discrepancia crítica que debe resolverse a nivel arquitectónico.
*   **Herencia de `BaseContextHandler`:** Se ha corregido para que herede de `BaseActionHandler`.

Para un detalle completo de estas y otras posibles inconsistencias, por favor consulte el archivo `refactorizado/common/inconsistencies.md`.
