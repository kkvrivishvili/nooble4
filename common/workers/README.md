# Módulo de Workers Comunes (`refactorizado/common/workers/`)

Este módulo proporciona la infraestructura base para los workers de los microservicios en el sistema Nooble4.

## Componentes Principales

### `BaseWorker`

`BaseWorker` es una clase abstracta diseñada para ser la superclase de todos los workers específicos de los servicios. Proporciona un ciclo de vida estandarizado y un mecanismo para procesar acciones (`DomainAction`) recibidas a través de colas de Redis.

#### Características Clave:

-   **Ciclo de Vida:** Define métodos como `setup()`, `run()`, `_process_action_loop()`, y `cleanup()` para una gestión estructurada del worker.
-   **Manejo de Acciones:** Implementa un bucle principal (`_process_action_loop`) que continuamente escucha en una cola de acciones de Redis (definida por `action_queue_name`).
-   **Descubrimiento Dinámico de Handlers:**
    -   Al recibir una `DomainAction`, `BaseWorker` utiliza el campo `action.action_type` (ej. "agent.run", "document.process") para encontrar dinámicamente un método handler apropiado dentro de la clase del worker que hereda de `BaseWorker`.
    -   El método handler esperado debe seguir la convención de nomenclatura `_handle_<action_type_part1>_<action_type_part2>_...()`. Por ejemplo, para una acción con `action_type = "document.process"`, `BaseWorker` buscará un método llamado `_handle_document_process()`.
    -   Si no se encuentra un handler específico, se lanza una excepción `HandlerNotFoundError`.
-   **Procesamiento de Acciones:** Una vez encontrado el handler, se invoca con la `DomainAction` como argumento. El resultado del handler (que puede ser una `DomainActionResponse` o datos para construir una) se utiliza para responder, si es necesario.
-   **Integración con Redis:** Utiliza una instancia de `RedisPool` para las conexiones a Redis y un `QueueManager` para la nomenclatura de colas (aunque existen inconsistencias actuales, ver abajo).
-   **Señal de Parada:** Escucha una señal de parada (`stop_event`) para terminar su ejecución de forma controlada.

### `HandlerNotFoundError`

Una excepción personalizada que se lanza cuando `BaseWorker` no puede encontrar un método handler para un `action_type` específico.

## Inconsistencias y Puntos de Mejora

Existen algunas inconsistencias y áreas de mejora identificadas para este módulo y su interacción con otros componentes comunes. Para más detalles, por favor consulte el archivo centralizado de inconsistencias:

-   [`../../inconsistencias.md`](../../inconsistencias.md)

En particular, los puntos relevantes para `BaseWorker` incluyen:

-   El uso síncrono de `RedisPool` (que es asíncrono).
-   La instanciación y uso de `QueueManager` que no se alinea con la definición actual de `QueueManager`.

## Uso

Para crear un nuevo worker para un servicio:

1.  Cree una nueva clase que herede de `BaseWorker`.
2.  Implemente el método abstracto `_initialize_handlers()` (aunque la tendencia actual es hacia `_handle_action` y un registro más explícito o descubrimiento dinámico mejorado, este método aún puede ser parte del patrón heredado en algunos workers).
3.  Defina métodos `_handle_<action_type>()` para cada tipo de acción que el worker deba procesar.
4.  En el punto de entrada de su servicio (ej. `main.py`), instancie su worker y llame a su método `run()`.

```python
# Ejemplo (conceptual)
from refactorizado.common.workers import BaseWorker
from refactorizado.common.models import DomainAction, DomainActionResponse

class MiWorkerEspecifico(BaseWorker):
    async def _initialize_components(self):
        # Inicializar cualquier componente específico del worker si es necesario
        await super()._initialize_components() # Llama a la inicialización del BaseWorker

    async def _handle_mi_accion_especifica(self, action: DomainAction) -> DomainActionResponse:
        # Lógica para manejar 'mi.accion.especifica'
        print(f"Procesando acción: {action.action_type} con datos: {action.data}")
        # ... hacer trabajo ...
        return DomainActionResponse(
            action_type=action.action_type + ".response",
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            status_code=200,
            data={"resultado": "éxito"}
        )

    async def _handle_otra_accion(self, action: DomainAction) -> dict:
        # Lógica para manejar 'otra.accion'
        # ... hacer trabajo ...
        # Puede devolver un dict que se usará para construir DomainActionResponse
        return {"mensaje": "Procesado correctamente"}

# En algún lugar de la inicialización del servicio:
# settings = get_settings() # Cargar configuración
# redis_pool = RedisPool(settings=settings)
# await redis_pool.connect()
# mi_worker = MiWorkerEspecifico(service_name="mi_servicio", settings=settings, redis_pool=redis_pool)
# asyncio.create_task(mi_worker.run())
```
