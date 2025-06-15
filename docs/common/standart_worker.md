# Estándar de Workers en Nooble4 (Redis Streams y BaseService)

> **Última Revisión:** 15 de Junio de 2025
> **Estado:** Aprobado y en implementación.
> **Clase Base de Referencia:** `common.workers.base_worker.BaseWorker`
> **Servicio Base de Referencia:** `common.services.base_service.BaseService`

## 1. Introducción y Filosofía

Este documento describe la arquitectura estándar para los `Workers` en Nooble4. Los Workers son componentes cruciales que actúan como consumidores de mensajes de **Redis Streams** y orquestan el procesamiento de `DomainAction`s.

La filosofía central es la **separación de responsabilidades**:
-   El `BaseWorker` es un componente de **infraestructura**. Se encarga de la comunicación con Redis Streams (consumo de mensajes, acknowledgements), deserialización de `DomainAction`s, y manejo básico del ciclo de vida de la acción.
-   Toda la **lógica de negocio** reside en una instancia de un servicio derivado de `common.services.base_service.BaseService`. El Worker delega el procesamiento de cada `DomainAction` a este servicio.

**Responsabilidades Clave del Worker (derivado de `BaseWorker`):**
-   Inicializar y mantener una instancia de su `BaseService` correspondiente (esto se hace externamente y se inyecta al worker).
-   Implementar el método `_handle_action` para pasar la `DomainAction` recibida al método `process_action` de su servicio inyectado.

**Lo que un Worker NO debe hacer:**
-   Contener lógica de negocio directa (validaciones de dominio, acceso a bases de datos, llamadas a APIs externas).
-   Conocer los detalles internos de cómo se procesa una acción más allá de la delegación.

## 2. La Clase Base: `common.workers.base_worker.BaseWorker`

`BaseWorker` proporciona la infraestructura fundamental para todos los workers del sistema.

### 2.1. Inicialización

El constructor (`__init__`) de `BaseWorker` recibe:
-   `app_settings`: El objeto de configuración específico del servicio (ej. `EmbeddingServiceSettings`). Este objeto debe heredar de `CommonAppSettings`.
-   `async_redis_conn`: Una conexión de `redis.asyncio.Redis` ya inicializada y gestionada externamente (normalmente por `RedisManager` a nivel de aplicación del servicio).
-   `service_instance`: Una instancia del servicio (derivado de `BaseService`) que manejará la lógica de negocio. Esta se inyecta al worker.
-   `consumer_id_suffix` (Opcional): Un sufijo para el ID del consumidor, útil si se ejecutan múltiples instancias del mismo worker.

Dentro del constructor, `BaseWorker` inicializa:
-   `self.queue_manager`: Para generar nombres de streams y grupos de consumidores estandarizados.
-   `self.redis_client`: Una instancia de `BaseRedisClient` para que el worker pueda, si es necesario, actuar como cliente de otros servicios. Utiliza la `async_redis_conn` provista.
-   `self.service_name`: Extraído de los `app_settings`.
-   `self.service`: La instancia del servicio de negocio (`BaseService`) que se le pasó.
-   `self._logger`: Un logger configurado.
-   Configuración para el consumo de Redis Streams (nombre del stream, nombre del grupo consumidor, ID del consumidor).

### 2.2. Flujo de Ejecución (`run` y `_process_action_loop`)

1.  El método `async def run()` es el punto de entrada para iniciar el worker.
2.  `run()` primero llama a `_ensure_consumer_group_exists()` para crear el stream y el grupo de consumidores en Redis si no existen.
3.  Luego, inicia el bucle principal, `_process_action_loop()`.
4.  `_process_action_loop()` escucha indefinidamente en el **Redis Stream** configurado para el servicio, utilizando `XREADGROUP` para leer mensajes como parte de un grupo de consumidores. Esto permite que múltiples instancias del worker compartan la carga de trabajo (patrón de consumidor competitivo).
5.  Cuando llega un mensaje (`DomainAction` serializado):
    a.  Se deserializa y valida el `DomainAction`.
    b.  Se invoca `await self._handle_action(action)`.
    c.  El resultado de `_handle_action` (que es el resultado de `self.service.process_action(action)`) se utiliza para determinar cómo responder:
        i.  Si la `DomainAction` original era pseudo-síncrona (tenía `callback_queue_name` y `_handle_action` devolvió un resultado), `BaseWorker` envía una `DomainActionResponse` a la cola de respuesta especificada.
        ii. Si la `DomainAction` original tenía `callback_action_type` y `callback_queue_name` (para un callback asíncrono) y `_handle_action` devolvió un resultado, `BaseWorker` construye y envía un nuevo `DomainAction` (el callback) a la `callback_queue_name`.
    d.  Finalmente, el mensaje se confirma (acknowledged) en el Stream usando `XACK`.
6.  El bucle maneja errores, reintentos configurables para el procesamiento de acciones, y el manejo de mensajes pendientes si el worker se reinicia.

### 2.3. El Contrato: `_handle_action`

Este es el único método abstracto que un worker hijo **DEBE** implementar.

`async def _handle_action(self, action: DomainAction) -> Optional[Any]:`

-   **Responsabilidad Principal**: Delegar el procesamiento de la `DomainAction` a la instancia de `BaseService` que el worker gestiona (que le fue inyectada).
-   **Implementación Típica**: `return await self.service.process_action(action)`
-   **Retorno**:
    -   El valor devuelto por `self.service.process_action(action)`. Este valor será utilizado por `BaseWorker` para construir la `DomainActionResponse` (en casos pseudo-síncronos) o el `DomainAction` de callback.
    -   Si `self.service.process_action(action)` devuelve `None` (o no devuelve nada), se asume que no hay una respuesta directa o callback que enviar desde `BaseWorker` (aunque el servicio podría haber enviado algo internamente).
    -   Si `self.service.process_action(action)` lanza una excepción, `BaseWorker` la capturará. Si la acción original era pseudo-síncrona, se enviará una `DomainActionResponse` de error. La excepción también se registrará.

## 3. Cómo Implementar un Nuevo Worker

**Paso 1: Crear la Clase del Servicio de Negocio (heredando de `BaseService`)**

Primero, define tu servicio que contendrá la lógica de negocio.

```python
# en mi_servicio/services/mi_logica_service.py
from common.services.base_service import BaseService
from common.models.actions import DomainAction
from common.config.common_app_settings import CommonAppSettings # o tu settings específico
from redis.asyncio import Redis as AIORedis
from typing import Any, Optional

class MiLogicaService(BaseService):
    def __init__(self, app_settings: CommonAppSettings, direct_redis_conn: Optional[AIORedis] = None, service_redis_client: Optional[Any] = None):
        # Nota: service_redis_client se pasa a super() pero puede ser None si el servicio no lo necesita directamente.
        super().__init__(app_settings=app_settings, service_redis_client=service_redis_client, direct_redis_conn=direct_redis_conn)
        # Inicializa cualquier otro componente que el servicio necesite
        # self.mi_componente = MiComponente(...)

    async def process_action(self, action: DomainAction) -> Any:
        self._logger.info(f"MiLogicaService procesando action: {action.action_type}")
        
        # Validar action.data con un modelo Pydantic específico si es necesario
        # from mi_servicio.models.schemas import MiAccionDataModel
        # validated_data = MiAccionDataModel(**action.data)

        if action.action_type == "mi_servicio.accion.hacer_algo":
            # ... lógica de negocio para hacer_algo ...
            # puede usar self.direct_redis_conn o self.service_redis_client si se configuró
            resultado = {"status": "completado desde MiLogicaService", "detalle": action.action_type}
            return resultado
        
        elif action.action_type == "mi_servicio.accion.notificar":
            # ... lógica de negocio para notificar (fire-and-forget) ...
            self._logger.info("Notificación procesada por MiLogicaService")
            return None # No hay respuesta directa o callback desde BaseWorker
            
        else:
            self._logger.warning(f"MiLogicaService no maneja la acción: {action.action_type}")
            raise NotImplementedError(f"Acción no soportada por MiLogicaService: {action.action_type}")

```

**Paso 2: Crear la Clase del Worker (heredando de `BaseWorker`)**

```python
# en mi_servicio/workers/mi_worker.py
from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.config.common_app_settings import CommonAppSettings # o tu settings específico
from redis.asyncio import Redis as AIORedis
from typing import Any, Optional

# Importa tu servicio
from mi_servicio.services.mi_logica_service import MiLogicaService

class MiWorker(BaseWorker):
    def __init__(self, 
                 app_settings: CommonAppSettings, 
                 async_redis_conn: AIORedis, 
                 service_instance: MiLogicaService, # Inyecta la instancia del servicio
                 consumer_id_suffix: Optional[str] = None):
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn,
            service_instance=service_instance, # Pasa la instancia a BaseWorker
            consumer_id_suffix=consumer_id_suffix
        )
        # BaseWorker ya asigna service_instance a self.service

    async def _handle_action(self, action: DomainAction) -> Optional[Any]:
        """
        Delega el procesamiento de la acción al servicio de negocio inyectado.
        """
        self._logger.debug(f"MiWorker delegando acción {action.action_type} a {self.service.__class__.__name__}")
        return await self.service.process_action(action)

```

**Paso 3: Instanciación y Ejecución del Worker (generalmente en `main.py` o un script de arranque)**

```python
# en mi_servicio/main.py (ejemplo simplificado)
import asyncio
import redis.asyncio as redis
# from mi_servicio.config.mi_config import MiServicioSettings # Tus settings específicos
from common.config.common_app_settings import CommonAppSettings # Usar CommonAppSettings o uno derivado
from mi_servicio.workers.mi_worker import MiWorker
from mi_servicio.services.mi_logica_service import MiLogicaService
from common.clients.redis_manager import RedisManager 

async def main():
    # settings = MiServicioSettings() # Carga tu configuración específica
    settings = CommonAppSettings(service_name="mi_servicio_example") # Ejemplo con CommonAppSettings
    
    redis_manager = RedisManager(settings)
    await redis_manager.initialize()
    
    worker_redis_conn = await redis_manager.get_redis_connection()
    
    # Crear instancia del servicio de negocio
    # El servicio puede necesitar su propio BaseRedisClient para comunicarse con otros servicios,
    # o acceso directo a Redis. Aquí se le pasa la conexión para acceso directo.
    # Si MiLogicaService usa un BaseRedisClient, este se crearía dentro de su __init__.
    mi_logica_service_instance = MiLogicaService(app_settings=settings, direct_redis_conn=worker_redis_conn)

    worker_instance = MiWorker(
        app_settings=settings,
        async_redis_conn=worker_redis_conn,
        service_instance=mi_logica_service_instance,
        consumer_id_suffix="instance1" 
    )

    try:
        print(f"Iniciando MiWorker para el servicio: {settings.service_name}...")
        await worker_instance.run()
    except KeyboardInterrupt:
        print("MiWorker detenido por el usuario.")
    finally:
        print("Cerrando MiWorker y conexiones Redis...")
        await worker_instance.stop()
        await redis_manager.close()
        print("Limpieza completa.")

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Concurrencia Interna en el Servicio (Opcional)

Si un `BaseService` necesita procesar partes de una `DomainAction` de forma concurrente (ej. llamar a múltiples APIs externas), puede usar `asyncio.gather()` internamente dentro de su método `process_action`. El `BaseWorker` en sí mismo procesa una `DomainAction` a la vez desde su perspectiva de bucle principal, pero el servicio es libre de usar concurrencia asyncio para optimizar el manejo de esa única acción.

Para procesar múltiples `DomainAction`s de Redis Streams concurrentemente, se deben ejecutar múltiples instancias del Worker (ya sea como procesos separados o como tareas asyncio separadas gestionadas por un orquestador a nivel de aplicación de servicio). `BaseWorker` con su uso de grupos de consumidores de Redis Streams está diseñado para soportar este patrón de escalado horizontal.

## 5. Conclusión

La arquitectura `BaseWorker` junto con `BaseService` promueve un diseño limpio y desacoplado:
-   **Workers como Infraestructura**: Manejan la comunicación con Redis Streams.
-   **Servicios como Lógica de Negocio**: Contienen la lógica específica de la aplicación.

Este enfoque simplifica el desarrollo, mejora la testeabilidad y proporciona un marco robusto y consistente para construir microservicios reactivos en Nooble4.
