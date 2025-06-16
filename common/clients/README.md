# Módulo de Clientes Comunes (`common/clients/`)

Este módulo proporciona componentes estandarizados para la gestión de conexiones Redis y la comunicación entre microservicios mediante el envío de `DomainAction`.

## Componentes Principales

### 1. `RedisManager`

`RedisManager` es responsable de centralizar la creación, gestión y cierre de las conexiones Redis asíncronas (`redis.asyncio.Redis`) que utilizan los servicios.

#### Propósito:
-   Abstraer la configuración y el ciclo de vida de la conexión Redis.
-   Proporcionar un pool de conexiones Redis eficiente y reutilizable para los componentes del servicio (como `BaseRedisClient` y `BaseWorker`).

#### Configuración:
-   Se inicializa con una instancia de `CommonAppSettings` (generalmente parte de las settings específicas de un servicio).
-   Parámetros clave de `CommonAppSettings` utilizados:
    -   `redis_url`: La URL para conectarse a Redis.
    -   `redis_socket_keepalive`: Booleano para habilitar keepalive en el socket.
    -   `redis_socket_keepalive_options`: Diccionario con opciones de keepalive TCP.

#### Ciclo de Vida y Uso:
Debe ser gestionado a nivel de servicio, típicamente durante el inicio y apagado de la aplicación.

1.  **Instanciación e Inicialización (al inicio del servicio):
    ```python
    # En el main.py de un servicio (ej. usando FastAPI)
    import asyncio
    from common.clients.redis_manager import RedisManager
    # from your_service.config import service_settings # Suponiendo que carga CommonAppSettings

    # Ejemplo de carga de settings (debe adaptarse a su implementación)
    # from common.config import CommonAppSettings
    # class MockServiceSettings:
    #     service_name = "my_service"
    #     common_settings = CommonAppSettings(redis_url="redis://localhost", environment="dev", service_name="my_service")
    # service_settings = MockServiceSettings()

    # async def startup_service():
    #     global redis_manager, redis_connection
    #     redis_manager = RedisManager(settings=service_settings.common_settings)
    #     await redis_manager.initialize()
    #     redis_connection = redis_manager.get_client()
    #     # redis_connection ahora puede ser usado por BaseRedisClient o BaseWorker
    ```

2.  **Obtención de la Conexión:**
    ```python
    # redis_conn = redis_manager.get_client()
    ```
    El cliente devuelto es una instancia de `redis.asyncio.Redis` (generalmente un pool de conexiones).

3.  **Cierre (al apagar el servicio):**
    ```python
    # async def shutdown_service():
    #     if redis_manager:
    #         await redis_manager.close()
    ```

### 2. `BaseRedisClient`

`BaseRedisClient` es un cliente estandarizado para que los servicios envíen `DomainAction` a otros servicios a través de Redis. Ahora utiliza Redis Streams para la mayoría de los envíos asíncronos.

#### Propósito:
-   Proporcionar una API consistente para los diferentes patrones de comunicación entre servicios (asíncrono, pseudo-síncrono, asíncrono con callback).
-   Encapsular la lógica de serialización de `DomainAction` y la interacción con Redis (comandos `XADD` para streams, `LPUSH`/`BRPOP` para colas de respuesta).

#### Configuración:
-   Se inicializa con:
    -   `service_name: str`: El nombre del servicio que está utilizando este cliente (se usa como `origin_service` en las `DomainAction`).
    -   `redis_client: redis.asyncio.Redis`: La conexión/pool Redis obtenida de `RedisManager`.
    -   `settings: CommonAppSettings`: Para acceder a configuraciones como el `environment` (usado por `QueueManager` internamente).

#### Métodos Principales y Uso:

El `BaseRedisClient` utiliza internamente un `QueueManager` (inicializado con `settings.environment`) para determinar los nombres de los streams y colas de respuesta.

1.  **`async def send_action_async(self, action: DomainAction)`**
    -   Envía una `DomainAction` de forma asíncrona (fire-and-forget).
    -   La acción se envía a un **Redis Stream** usando `XADD`. El nombre del stream se obtiene de `QueueManager.get_service_action_stream(target_service)`.
    -   El payload de la `DomainAction` (JSON) se almacena en el stream bajo la clave `'data'`.

2.  **`async def send_action_pseudo_sync(self, action: DomainAction, timeout: int = 30) -> Optional[DomainActionResponse]`**
    -   Implementa un patrón de solicitud-respuesta pseudo-síncrono.
    -   **Solicitud:** La `DomainAction` inicial se envía a un **Redis Stream** del servicio destino (usando `XADD`, igual que `send_action_async`).
    -   **Respuesta:** Espera una `DomainActionResponse` en una **lista Redis temporal y única** (usando `BRPOP`). El nombre de esta cola de respuesta se genera con `QueueManager.get_response_queue()` y se pasa en `action.callback_queue_name`.

3.  **`async def send_action_async_with_callback(self, action: DomainAction, callback_event_name: str, callback_context: Optional[str] = None)`**
    -   Envía una `DomainAction` y espera un callback (otra `DomainAction`) en una cola específica.
    -   `callback_event_name` (str): El tipo de acción que se espera como callback (se asigna a `action.callback_action_type`).
    -   `callback_context` (Optional[str]): Un contexto opcional para el callback (actualmente no influye en la generación del nombre de la cola de callback por `QueueManager` pero está presente en la firma).
    -   **Solicitud Inicial:** La `DomainAction` se envía a un **Redis Stream** del servicio destino (usando `XADD`).
    -   **Callback:** El servicio que envía la acción espera que el servicio destino, una vez procesada la solicitud, envíe una nueva `DomainAction` (el callback) a la cola especificada en `action.callback_queue_name`. Esta cola de callback sigue siendo una lista Redis simple.

**Ejemplo de Instanciación y Uso:**

```python
# # Asumiendo redis_connection (de RedisManager) y service_settings están disponibles
# from common.clients import BaseRedisClient
# from common.models.actions import DomainAction
# # from common.config import CommonAppSettings

# # common_settings = service_settings.common_settings
# # base_redis_client = BaseRedisClient(
# #     service_name=service_settings.service_name,
# #     redis_client=redis_connection,
# #     settings=common_settings
# # )

# # action_to_send = DomainAction(
# #     action_id=str(uuid.uuid4()),
# #     action_type="another_service.do_something",
# #     data={"key": "value"}
# #     # ... otros campos necesarios
# # )

# # await base_redis_client.send_action_async(action_to_send)
```

### 3. `RedisStateManager`

`RedisStateManager` es una utilidad genérica para gestionar la persistencia de objetos de estado (modelos Pydantic) en Redis. Facilita el ciclo de vida de cargar, guardar y eliminar datos estructurados, manejando la serialización JSON y la validación Pydantic.

#### Propósito:
-   Abstraer la lógica de interacción con Redis para la persistencia de estados de aplicación, contextos de usuario, etc.
-   Asegurar que los datos se validen contra un modelo Pydantic al cargar y se serialicen correctamente al guardar.

#### Configuración:
-   Se inicializa con:
    -   `redis_conn: redis.asyncio.Redis`: La conexión/pool Redis obtenida de `RedisManager`.
    -   `state_model: Type[TStateModel]`: El modelo Pydantic (genérico `TStateModel`) que define la estructura del estado a gestionar.
    -   `app_settings: CommonAppSettings`: Para la configuración del logger, utilizando `app_settings.service_name`.

#### Métodos Principales y Uso:

1.  **`async def load_state(self, state_key: str) -> Optional[TStateModel]`**
    -   Carga y deserializa el estado desde Redis usando la `state_key` proporcionada.
    -   Retorna una instancia del `state_model` si se encuentra y valida, o `None`.

2.  **`async def save_state(self, state_key: str, state_data: TStateModel, expiration_seconds: Optional[int] = None)`**
    -   Guarda la instancia `state_data` del `state_model` en Redis bajo la `state_key`.
    -   Opcionalmente, puede establecer un tiempo de expiración (`expiration_seconds`).
    -   Lanza `TypeError` si `state_data` es `None` (para borrados, se debe usar `delete_state`).

3.  **`async def delete_state(self, state_key: str) -> bool`**
    -   Elimina el estado de Redis para la `state_key` dada.
    -   Retorna `True` si la clave fue eliminada, `False` si no existía.

**Ejemplo de Instanciación y Uso (dentro de un `BaseService`):**

```python
# # En un servicio que gestiona el estado de una sesión de usuario
# from common.clients import RedisStateManager
# from common.models.user_session import UserSessionState # Modelo Pydantic para el estado
# # Asumiendo que self.direct_redis_conn y self.app_settings están disponibles en el servicio

# class UserSessionService(BaseService):
#     async def __init__(self, app_settings, service_redis_client=None, direct_redis_conn=None):
#         super().__init__(app_settings, service_redis_client, direct_redis_conn)
#         if not direct_redis_conn:
#             raise ValueError("UserSessionService requiere direct_redis_conn para RedisStateManager")
#         self.session_state_manager = RedisStateManager[UserSessionState](
#             redis_conn=direct_redis_conn,
#             state_model=UserSessionState,
#             app_settings=app_settings
#         )

#     async def get_user_session(self, user_id: str) -> Optional[UserSessionState]:
#         session_key = f"user_session:{user_id}"
#         return await self.session_state_manager.load_state(session_key)

#     async def update_user_session(self, user_id: str, session_data: UserSessionState):
#         session_key = f"user_session:{user_id}"
#         await self.session_state_manager.save_state(session_key, session_data, expiration_seconds=3600)
```

## Interacción y Flujo General

1.  Un servicio, al iniciarse, crea y gestiona una instancia de `RedisManager`.
2.  Para enviar acciones, el servicio instancia `BaseRedisClient`, proporcionándole la conexión de `RedisManager` y su configuración.
3.  Cuando `BaseRedisClient` envía una acción, esta (generalmente) va a un Redis Stream.
4.  En el servicio destino, una o varias instancias de `BaseWorker` (o sus subclases) están escuchando ese stream como parte de un grupo de consumidores.
5.  `BaseWorker` procesa la acción y, si es necesario (pseudo-síncrono o con callback), utiliza su propio `BaseRedisClient` interno para enviar la respuesta/callback a la cola especificada en la `DomainAction` original.

Este desacoplamiento mediante Redis Streams y listas para respuestas/callbacks permite una comunicación inter-servicios escalable y robusta.
