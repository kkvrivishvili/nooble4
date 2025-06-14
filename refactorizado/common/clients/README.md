# Módulo de Clientes Comunes (`refactorizado.common.clients`)

Este módulo está destinado a proporcionar clientes estandarizados para la comunicación entre los microservicios de Nooble4. Actualmente, contiene `BaseRedisClient`.

**¡ADVERTENCIA IMPORTANTE!**
El `BaseRedisClient` actual presenta **inconsistencias críticas** con otros módulos comunes (`RedisPool`, `QueueManager`) que lo hacen **inoperable en su estado actual** con la infraestructura común refactorizada. Estos problemas deben resolverse antes de que pueda ser utilizado de manera efectiva.

## `BaseRedisClient`

El `BaseRedisClient` está diseñado (pero actualmente implementado con problemas) para facilitar la comunicación basada en colas de Redis entre servicios.

### Funcionalidad Prevista

-   **Comunicación vía Redis:** Utilizar Redis como broker de mensajes.
-   **Gestión de Conexiones:** Apoyarse en un pool de conexiones Redis.
-   **Nomenclatura de Colas:** Emplear un gestor de colas para nombres consistentes.
-   **Modelos de Datos Estándar:** Usar `DomainAction` y `DomainActionResponse`.
-   **Identificación del Origen y `correlation_id`**: Manejar `origin_service` y `correlation_id`.

### Patrones de Comunicación Implementados (Conceptualmente)

1.  **`send_action_async(action: DomainAction)`:** Envío asíncrono (fire-and-forget).
2.  **`send_action_pseudo_sync(action: DomainAction, timeout: int = 30) -> DomainActionResponse`:** Envío con espera bloqueante de respuesta.

### Problemas Críticos y Puntos Pendientes

Los siguientes problemas deben abordarse para que `BaseRedisClient` sea funcional y coherente con el resto de los módulos comunes en `refactorizado/common/`:

1.  **Conflicto Síncrono/Asíncrono (CRÍTICO):**
    *   `BaseRedisClient` es **síncrono** (usa `redis.Redis`).
    *   El `RedisPool` común (`refactorizado.common.redis_pool.RedisPool`) es **asíncrono** (usa `redis.asyncio`).
    *   **Son incompatibles.** `BaseRedisClient` necesita ser refactorizado para operar de forma asíncrona o se debe proporcionar una alternativa de pool síncrono (lo que iría en contra de la modernización general hacia `asyncio`).

2.  **Importación Incorrecta de `RedisPool`:**
    *   Actualmente importa `RedisPool` desde `refactorizado.common.db.redis_pool` (ruta incorrecta y probablemente referenciando una versión síncrona antigua).
    *   Debe apuntar a `refactorizado.common.redis_pool.RedisPool` y adaptarse a su naturaleza asíncrona.

3.  **Uso Incorrecto de `QueueManager`:**
    *   La instanciación de `QueueManager` en `BaseRedisClient.__init__` es incorrecta (pasa `service_name` en lugar de `prefix` y `environment`).
    *   Las llamadas a los métodos de `QueueManager` (ej., `get_service_action_queue`, `get_response_queue`) no coinciden con las firmas de los métodos definidos en `refactorizado.common.utils.queue_manager.QueueManager`.

4.  **Patrón `send_action_async_with_callback` Faltante:**
    *   Este patrón, crucial para operaciones de larga duración no bloqueantes con notificación, no está implementado.

5.  **Gestión de `trace_id`:**
    *   No hay una propagación explícita o generación de `trace_id` facilitada por el cliente.

**Referencia a Inconsistencias:**

Para un análisis más detallado de estos problemas, consulte el archivo `refactorizado/inconsistencies.md` (sección "Módulo `base_redis_client.py`").

### Uso Básico (Conceptual - NO FUNCIONAL ACTUALMENTE)

El siguiente ejemplo de código es conceptual y **no funcionará** hasta que se resuelvan los problemas mencionados.

```python
# Asumiendo que los problemas se han resuelto y las importaciones son correctas:
# from refactorizado.common.redis_pool import get_redis_client, close_redis_pool # Asíncrono
# from refactorizado.common.clients import BaseRedisClient # Ahora asíncrono
# from refactorizado.common.models.actions import DomainAction
# from refactorizado.common.config import CommonAppSettings
# import asyncio
# import uuid

# async def ejemplo_uso():
#     app_settings = CommonAppSettings(service_name="mi_servicio_cliente", log_level="INFO", redis_url="redis://localhost")
#     redis_connection = await get_redis_client(app_settings)

#     # BaseRedisClient necesitaría ser adaptado para recibir una conexión asíncrona o el pool asíncrono
#     # y sus métodos internos deberían ser 'async'
#     redis_client = BaseRedisClient(service_name="mi_servicio_cliente", redis_conn=redis_connection) # Adaptación necesaria

#     mi_accion = DomainAction(
#         action_type="servicio_destino.entidad.verbo",
#         data={"clave": "valor"}
#     )

#     # Ejemplo de envío asíncrono (debería ser 'await')
#     # await redis_client.send_action_async(action=mi_accion)

#     # Ejemplo de envío pseudo-síncrono (debería ser 'await')
#     try:
#         # respuesta = await redis_client.send_action_pseudo_sync(action=mi_accion, timeout=10)
#         # if respuesta.success:
#         #     print(f"Respuesta recibida: {respuesta.data}")
#         # else:
#         #     print(f"Error: {respuesta.error}")
#         pass # Placeholder
#     except TimeoutError:
#         print("La operación pseudo-síncrona excedió el tiempo de espera.")
#     except Exception as e:
#         print(f"Ocurrió un error: {e}")
#     finally:
#         await close_redis_pool()

# if __name__ == "__main__":
#     # asyncio.run(ejemplo_uso())
      pass
```

**Conclusión:**

El `BaseRedisClient` requiere una refactorización significativa para alinearse con los componentes comunes asíncronos (`RedisPool`) y para utilizar correctamente `QueueManager`. Hasta que esto ocurra, no es un componente fiable para la comunicación inter-servicios en la arquitectura refactorizada.
