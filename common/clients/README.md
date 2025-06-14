# Módulo de Clientes Comunes (`refactorizado.common.clients`)

Este módulo proporciona clientes estandarizados para la comunicación entre los microservicios de Nooble4. Actualmente, su componente principal es el `BaseRedisClient`.

## `BaseRedisClient`

El `BaseRedisClient` facilita la comunicación asíncrona basada en colas de Redis entre los diferentes servicios de la aplicación. Ha sido refactorizado para operar de manera asíncrona utilizando `redis.asyncio` y para integrarse correctamente con `CommonAppSettings` y `QueueManager`.

### Características Principales:

-   **Operaciones Asíncronas:** Todos los métodos de comunicación con Redis son `async` y utilizan un cliente Redis asíncrono (`redis.asyncio.Redis`) que se pasa durante la inicialización.
-   **Integración con `CommonAppSettings`:** Recibe una instancia de `CommonAppSettings` para acceder a configuraciones globales como `service_name`.
-   **Uso de `QueueManager`:** Emplea una instancia de `QueueManager` (inicializada con `CommonAppSettings`) para determinar de forma consistente los nombres de las colas de acciones y respuestas.
-   **Modelos de Datos Estándar:** Utiliza los modelos `DomainAction` y `DomainActionResponse` de `refactorizado.common.models` para la serialización y deserialización de mensajes.
-   **Propagación de IDs:** Asegura la propagación de `correlation_id` y `trace_id` en los mensajes.
-   **Logging Detallado:** Incorpora logging para el seguimiento de las operaciones de envío y recepción.

### Patrones de Comunicación Implementados:

1.  **`async send_action_async(self, action: DomainAction, target_service: Optional[str] = None, specific_queue: Optional[str] = None)`**
    *   Envía una `DomainAction` de forma asíncrona (fire-and-forget) a la cola de acciones del servicio destino o a una cola específica.

2.  **`async send_action_pseudo_sync(self, action: DomainAction, timeout_seconds: int, target_service: Optional[str] = None, specific_queue: Optional[str] = None) -> DomainActionResponse`**
    *   Envía una `DomainAction` y espera de forma bloqueante (pero asíncrona internamente) una `DomainActionResponse` en una cola de respuesta temporal y única.
    *   Genera un `correlation_id` si no está presente en la acción original.
    *   Maneja timeouts y errores de Redis durante la espera.

3.  **`async send_action_async_with_callback(self, action: DomainAction, target_service: Optional[str] = None, specific_queue: Optional[str] = None)`**
    *   Envía una `DomainAction` de forma asíncrona, especificando en la acción original (`action.callback_queue_name` y `action.callback_action_type`) dónde y cómo se espera un callback.
    *   El servicio receptor es responsable de enviar una nueva `DomainAction` (el callback) a la `callback_queue_name` especificada.

4.  **`async send_message_to_queue_async(self, queue_name: str, message: Union[DomainAction, DomainActionResponse, dict, str])`**
    *   Método de bajo nivel para enviar un mensaje (serializado a JSON si es un modelo Pydantic) a una cola específica.

5.  **`async wait_for_response(self, response_queue_name: str, correlation_id: str, timeout_seconds: int) -> DomainActionResponse`**
    *   Escucha en una cola específica por un mensaje que coincida con el `correlation_id` esperado, con un timeout.

### Inicialización y Uso:

```python
import asyncio
from refactorizado.common.clients import BaseRedisClient
from refactorizado.common.models import DomainAction, DomainActionResponse
from refactorizado.common.config import CommonAppSettings # Asumiendo una clase de settings específica
from refactorizado.common.utils import QueueManager
import redis.asyncio as redis # Importante: usar el cliente asyncio

async def main():
    # 1. Configuración y Pool de Redis (esto usualmente se gestionaría a nivel de aplicación)
    settings = CommonAppSettings(
        service_name="mi_servicio_origen",
        environment="dev",
        log_level="DEBUG",
        redis_url="redis://localhost:6379/0", # Asegúrate que tu URL es correcta
        # ... otros settings necesarios para CommonAppSettings
        redis_host="localhost", # Ejemplo, puede venir de redis_url
        redis_port=6379,      # Ejemplo
        default_queue_prefix="nooble4"
    )
    redis_pool = redis.ConnectionPool.from_url(settings.redis_url_with_db, decode_responses=True)
    redis_conn = redis.Redis(connection_pool=redis_pool)

    # 2. Inicializar QueueManager
    queue_manager = QueueManager(settings=settings)

    # 3. Inicializar BaseRedisClient
    # Nota: BaseRedisClient espera un cliente Redis ya conectado y las settings.
    client = BaseRedisClient(origin_service_name=settings.service_name, redis_client=redis_conn, app_settings=settings, queue_manager=queue_manager)

    # 4. Crear una DomainAction
    action_to_send = DomainAction(
        action_type="saludo.formal.procesar_nombre",
        data={"nombre": "Mundo"},
        tenant_id="test_tenant",
        user_id="test_user"
    )

    # 5. Usar uno de los patrones de envío
    # Ejemplo: Pseudo-síncrono
    try:
        print(f"Enviando acción pseudo-síncrona: {action_to_send.action_id}")
        response = await client.send_action_pseudo_sync(
            action=action_to_send,
            timeout_seconds=10,
            target_service="servicio_saludos" # El servicio que tiene el worker escuchando
        )
        if response.success:
            print(f"Respuesta recibida para {response.correlation_id}: {response.data}")
        else:
            print(f"Error en la respuesta para {response.correlation_id}: {response.error}")
    except TimeoutError:
        print(f"Timeout esperando respuesta para {action_to_send.action_id}")
    except Exception as e:
        print(f"Error durante send_action_pseudo_sync: {e}")

    # Ejemplo: Asíncrono fire-and-forget
    action_fire_forget = DomainAction(
        action_type="notificacion.log.registrar_evento",
        data={"evento": "Prueba de cliente completada"},
        tenant_id="test_tenant"
    )
    await client.send_action_async(action=action_fire_forget, target_service="servicio_logging")
    print(f"Acción fire-and-forget enviada: {action_fire_forget.action_id}")

    # Cerrar conexiones (en un escenario real, esto sería al apagar la app)
    await redis_conn.close()
    await redis_pool.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Consideraciones:

-   El `BaseRedisClient` está diseñado para ser un componente reutilizable dentro de cada microservicio que necesite comunicarse con otros a través de Redis.
-   La gestión del ciclo de vida del `redis_client` (conexión, desconexión) es responsabilidad del código que instancia `BaseRedisClient` (generalmente a nivel de aplicación del servicio).
-   Asegúrese de que los servicios receptores tengan workers que escuchen en las colas correctas (determinadas por `QueueManager`) y procesen las `DomainAction` entrantes.
