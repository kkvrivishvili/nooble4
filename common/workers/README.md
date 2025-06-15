# Módulo de Workers Comunes (`common/workers/`)

Este módulo define la **Infraestructura de Workers** para los microservicios. Los workers son componentes cruciales que procesan tareas de forma asíncrona, consumiendo `DomainAction` desde Redis Streams y delegando la lógica de negocio a la Capa de Servicio correspondiente.

## Componentes Principales

### `BaseWorker` (Versión 8.0+)

`BaseWorker` es una clase base abstracta (`ABC`) diseñada para ser la superclase de todos los workers específicos de los servicios. Implementa la lógica fundamental para interactuar con Redis Streams utilizando grupos de consumidores, asegurando un procesamiento de mensajes robusto y escalable.

#### Características Clave:

-   **Integración con Redis Streams:**
    -   **Consumo de Mensajes:** Utiliza `XREADGROUP` para leer mensajes de un stream de acciones específico del servicio. Esto permite que múltiples instancias de workers (consumidores) dentro del mismo grupo compartan la carga de trabajo del stream.
    -   **Grupos de Consumidores:** Automáticamente crea/verifica un grupo de consumidores (`consumer_group_name`, ej., `mi_servicio-group`) para el stream de acciones del servicio (`action_stream_name`) durante la inicialización.
    -   **Nombres de Consumidor Únicos:** Cada instancia de `BaseWorker` tiene un `consumer_name` único (ej., `mi_servicio-worker-suffix-uuid`), permitiendo a Redis rastrear los mensajes procesados por cada consumidor.
    -   **Confirmación de Mensajes (ACK):** Utiliza `XACK` para confirmar el procesamiento exitoso de un mensaje. Si el procesamiento falla, el mensaje no se confirma y puede ser reprocesado o reclamado por otro consumidor, asegurando la fiabilidad.
-   **Ciclo de Vida Estándar:**
    -   `__init__(app_settings, async_redis_conn, consumer_id_suffix=None)`: Constructor que inicializa el worker, configura nombres de stream/grupo/consumidor y el `BaseRedisClient` interno.
    -   `initialize()`: Asegura la existencia del grupo de consumidores. Debe ser llamado (o invocado por `run()`) antes de procesar acciones.
    -   `run()`: Inicia el bucle principal de procesamiento de acciones.
    -   `_process_action_loop()`: El bucle que continuamente lee, procesa y confirma mensajes del stream.
    -   `stop()`: Detiene el worker de forma segura.
-   **Manejo de Acciones Delegado:**
    -   Requiere la implementación del método abstracto `async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:` en las subclases. Este método contiene la lógica de negocio específica para procesar una `DomainAction`.
    -   Gestiona automáticamente el envío de respuestas para acciones pseudo-síncronas y el envío de callbacks para acciones asíncronas con callback, utilizando el `BaseRedisClient` interno.
-   **Configuración y Dependencias:**
    -   Recibe `CommonAppSettings` (o las settings del servicio que las contienen) para la configuración del servicio (nombre, entorno) y Redis.
    -   Recibe una conexión Redis asíncrona (`redis.asyncio.Redis`), que idealmente es gestionada y proporcionada por una instancia de `RedisManager` a nivel de servicio.
    -   Utiliza `QueueManager` para generar nombres consistentes para streams y colas de respuesta/callback.

## Uso y Patrones de Implementación

### 1. Crear un Worker Específico del Servicio

Para implementar un worker para un servicio (ej., `UserServiceWorker`):

```python
import logging
from typing import Dict, Any, Optional

from common.workers import BaseWorker
from common.models.actions import DomainAction
# from your_service_specific_logic import process_user_creation, process_user_update

logger = logging.getLogger(__name__)

class UserServiceWorker(BaseWorker):
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        logger.info(f"[{self.service_name} - {self.consumer_name}] Procesando acción: {action.action_type}")
        
        # Ejemplo de enrutamiento basado en action_type
        if action.action_type == "user.create":
            # result_data = await process_user_creation(action.data)
            # return result_data # Si la acción espera una respuesta/callback
            pass # Para fire-and-forget
        elif action.action_type == "user.update":
            # await process_user_update(action.data)
            pass
        else:
            logger.warning(f"Handler no implementado para {action.action_type}")
            raise NotImplementedError(f"No handler for {action.action_type}")
        
        return None # Por defecto para acciones fire-and-forget o si ya se manejó la respuesta
```

### 2. Ejecutar Múltiples Workers Internos en un Servicio

Para escalar el procesamiento de mensajes *dentro* de una única instancia de servicio, puedes ejecutar múltiples instancias de tu worker específico (o `BaseWorker` directamente si es genérico) como tareas asyncio. Cada tarea actuará como un consumidor independiente dentro del mismo grupo.

Esto se gestiona típicamente en el ciclo de vida de la aplicación del servicio (ej., usando eventos `startup` y `shutdown` en FastAPI).

**Ejemplo Conceptual (FastAPI `main.py`):**

```python
import asyncio
import logging
from typing import List, Optional
from fastapi import FastAPI

from common.clients.redis_manager import RedisManager
# from common.config.your_service_settings import YourServiceSettings # Tu modelo de settings
# from your_service.worker import YourServiceWorker # Tu worker específico

logger = logging.getLogger(__name__)
app = FastAPI()

redis_manager: Optional[RedisManager] = None
active_worker_tasks: List[asyncio.Task] = []
active_worker_instances: List[BaseWorker] = [] # Para llamar a stop()

NUM_INTERNAL_WORKERS = 4 # Configurable

@app.on_event("startup")
async def startup_event():
    global redis_manager, active_worker_tasks, active_worker_instances
    
    # app_settings = YourServiceSettings()
    # redis_manager = RedisManager(settings=app_settings.common_settings)
    # await redis_manager.initialize()
    # redis_connection = redis_manager.get_client()
    
    # --- Mock para el ejemplo --- 
    from common.config import CommonAppSettings
    from redis.asyncio import Redis
    class MockServiceSettings:
        service_name = "mock_service"
        common_settings = CommonAppSettings(redis_url="redis://localhost", environment="dev", service_name="mock_service")
    app_settings = MockServiceSettings()
    redis_manager = RedisManager(settings=app_settings.common_settings)
    await redis_manager.initialize()
    redis_connection = redis_manager.get_client()
    # --- Fin Mock ---

    logger.info(f"Iniciando {NUM_INTERNAL_WORKERS} workers para '{app_settings.service_name}'...")
    for i in range(NUM_INTERNAL_WORKERS):
        consumer_suffix = f"internal-{i}"
        # worker_instance = YourServiceWorker(
        # Reemplazar BaseWorker con tu implementación específica (ej. UserServiceWorker)
        worker_instance = BaseWorker(
            app_settings=app_settings, # O app_settings.common_settings si BaseWorker solo necesita eso
            async_redis_conn=redis_connection,
            consumer_id_suffix=consumer_suffix
        )
        # El método run() de BaseWorker llama a initialize() si es necesario.
        task = asyncio.create_task(worker_instance.run())
        active_worker_tasks.append(task)
        active_worker_instances.append(worker_instance)

    logger.info(f"{len(active_worker_tasks)} workers iniciados.")

@app.on_event("shutdown")
async def shutdown_event():
    global redis_manager, active_worker_tasks, active_worker_instances

    if active_worker_instances:
        logger.info(f"Deteniendo {len(active_worker_instances)} workers...")
        for worker_instance in active_worker_instances:
            await worker_instance.stop() # Señaliza a cada worker que se detenga
        # Opcionalmente, esperar a que las tareas realmente terminen:
        # await asyncio.gather(*active_worker_tasks, return_exceptions=True)
        logger.info("Workers detenidos.")
        active_worker_tasks.clear()
        active_worker_instances.clear()
        
    if redis_manager:
        await redis_manager.close()
        logger.info("RedisManager cerrado.")

# Resto de tu aplicación FastAPI...
```

#### Configuración Relevante:

-   **`CommonAppSettings` (dentro de las settings de cada servicio):**
    -   `service_name`: Usado para nombres de stream, grupo y consumidor.
    -   `environment`: Usado por `QueueManager` para prefijar nombres de stream/cola.
    -   `redis_url`, `redis_socket_keepalive`, etc.: Para la conexión Redis gestionada por `RedisManager`.
-   **`NUM_INTERNAL_WORKERS`**: Número de workers concurrentes a ejecutar por instancia de servicio. Puede ser una variable de entorno o configuración fija.

## Consideraciones Adicionales

-   **Manejo de Errores en `_handle_action`:** Las excepciones lanzadas dentro de `_handle_action` son capturadas por `BaseWorker`. Si la acción tenía una `callback_queue_name`, se intentará enviar una respuesta de error. Importante: el mensaje **no** será confirmado (ACKed) en Redis si `_handle_action` falla, permitiendo que sea reprocesado.
-   **Mensajes Malformados:** Si un mensaje en el stream no puede ser deserializado a `DomainAction` o le falta el campo `data`, `BaseWorker` lo registrará y lo confirmará (ACK) para evitar bucles de procesamiento con mensajes inválidos.
-   **Escalabilidad Horizontal:** Este patrón de workers internos permite un uso eficiente de los recursos de una instancia de servicio. Para mayor escalabilidad, se pueden desplegar múltiples instancias del servicio (ej. en diferentes contenedores o VMs), y Redis Streams distribuirá la carga entre todas ellas.

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
