# Gestor de Pool de Conexiones Redis Asíncrono (`refactorizado.common.redis_pool`)

Este módulo proporciona una clase `RedisPool` para gestionar de forma centralizada las conexiones a un servidor Redis utilizando la librería `redis.asyncio`, lo que lo hace adecuado para aplicaciones asíncronas.

## Características Principales

-   **Asíncrono:** Utiliza `redis.asyncio` para operaciones no bloqueantes, integrándose bien con `async/await` de Python.
-   **Patrón Singleton:** Asegura que solo exista una instancia de `RedisPool` y, por lo tanto, un único cliente (pool de conexiones) Redis subyacente por aplicación, optimizando recursos.
-   **Configuración Centralizada:** Obtiene los parámetros de conexión de una instancia de `CommonAppSettings` (de `refactorizado.common.config.base_settings`), permitiendo que la configuración de Redis se gestione junto con otras configuraciones de la aplicación.
    -   Parámetros utilizados: `redis_url`, `redis_decode_responses`, `redis_socket_connect_timeout`, `redis_max_connections`, `redis_health_check_interval`.
-   **Verificación de Conexión:** Realiza un `ping()` al servidor Redis durante la inicialización para asegurar que la conexión es exitosa antes de devolver el cliente.
-   **Gestión del Ciclo de Vida:** Proporciona métodos para obtener el cliente (`get_client` o `get_redis_client`) y para cerrar las conexiones del pool (`close` o `close_redis_pool`).

## Estructura del Módulo

-   **`RedisPool` (clase):**
    -   Implementa el patrón Singleton.
    -   `__new__(cls)`: Controla la creación de la instancia única.
    -   `async get_client(self, settings: CommonAppSettings) -> redis.Redis`:
        -   Crea y devuelve el cliente `redis.asyncio.Redis` si aún no existe.
        -   Utiliza `settings` para configurar la conexión.
        -   Realiza un `ping` inicial.
    -   `async close(self)`: Cierra el cliente Redis y limpia la instancia.

-   **`redis_pool` (instancia global):**
    -   Una instancia Singleton de `RedisPool` pre-creada para fácil acceso.

-   **Funciones Helper Asíncronas:**
    -   `async get_redis_client(settings: CommonAppSettings) -> redis.Redis`: Función de conveniencia para llamar a `redis_pool.get_client(settings)`.
    -   `async close_redis_pool()`: Función de conveniencia para llamar a `redis_pool.close()`.

## Uso Básico

```python
import asyncio
from refactorizado.common.redis_pool import get_redis_client, close_redis_pool
from refactorizado.common.config import CommonAppSettings # Asumiendo que CommonAppSettings está disponible y configurada

async def main():
    # Cargar o instanciar CommonAppSettings
    # Esto normalmente se haría una vez al inicio de la aplicación
    app_settings = CommonAppSettings(
        # Asegúrate de que redis_url y otros campos redis_* estén configurados,
        # ya sea directamente, vía variables de entorno o archivo .env
        redis_url="redis://localhost:6379/0",
        redis_decode_responses=True,
        # ... otros settings necesarios para CommonAppSettings
        service_name="mi_servicio_ejemplo", # Campo requerido por CommonAppSettings
        log_level="INFO" # Campo requerido por CommonAppSettings
    )

    redis_client = None
    try:
        # Obtener el cliente Redis del pool
        redis_client = await get_redis_client(app_settings)
        print("Cliente Redis obtenido exitosamente.")

        # Usar el cliente Redis
        await redis_client.set("mi_clave_async", "mi_valor_async")
        valor = await redis_client.get("mi_clave_async")
        print(f"Valor obtenido de Redis: {valor}")

    except Exception as e:
        print(f"Error durante la operación con Redis: {e}")
    finally:
        # Cerrar el pool de conexiones al final (generalmente al apagar la aplicación)
        # Nota: Si redis_client no se inicializó debido a un error en get_redis_client,
        # close_redis_pool() podría intentar cerrar un _redis_client que es None.
        # La implementación actual de close() maneja esto.
        await close_redis_pool()
        print("Pool de Redis cerrado.")

if __name__ == "__main__":
    asyncio.run(main())
```

## Puntos a Considerar y Mejoras Pendientes

Consultar `refactorizado/common/inconsistencies.md` (sección "Módulo `redis_pool`") para detalles, que incluyen:

-   **Incompatibilidad Síncrono/Asíncrono:** La principal preocupación es que este `RedisPool` es asíncrono, mientras que otros componentes comunes como `BaseRedisClient` son actualmente síncronos. Esto requiere una decisión arquitectónica para alinear el uso de Redis (síncrono vs. asíncrono) en todo el sistema o proporcionar implementaciones paralelas.
-   **Parámetros de Configuración Hardcodeados:** Los parámetros `socket_keepalive` y `socket_keepalive_options` están hardcodeados. Deberían ser configurables a través de `CommonAppSettings`.
-   **Claridad en `redis_url` vs. campos individuales:** `CommonAppSettings` define `redis_url` y también campos individuales de conexión Redis. Se debe clarificar la precedencia o el método preferido para configurar `RedisPool`.

Este módulo es fundamental para cualquier servicio que necesite interactuar con Redis de manera asíncrona.
