# Estándar de Workers en Nooble4 (Arquitectura v4.0)

> **Última Revisión:** 14 de Junio de 2024
> **Estado:** Aprobado y en implementación.
> **Clase de Referencia:** `common.workers.base_worker.BaseWorker`

## 1. Introducción y Filosofía

Este documento describe la arquitectura estándar para los `Workers` en Nooble4, que son el corazón de cada microservicio. El `BaseWorker` es una clase base abstracta que unifica la forma en que los servicios escuchan y procesan las acciones de las colas de Redis.

Los principios clave son:
- **Centralización de la Lógica**: El `Worker` es responsable tanto de la comunicación (escuchar en colas, enviar respuestas) como de la orquestación de la lógica de negocio.
- **Contrato Explícito**: Los workers hijos deben implementar un método abstracto (`_handle_action`), lo que garantiza una estructura consistente.
- **Simplicidad**: Se elimina la complejidad de la carga dinámica de handlers. El enrutamiento de acciones es un simple `if/elif/else` dentro del worker, lo que hace el flujo de código explícito y fácil de seguir.
- **Componentes Reutilizables**: El `BaseWorker` gestiona la conexión a Redis, la deserialización de mensajes y el ciclo de procesamiento, permitiendo que los desarrolladores se centren en la lógica de negocio.

## 2. La Clase Base: `BaseWorker`

La clase `BaseWorker` (`common/workers/base_worker.py`) proporciona la infraestructura fundamental para todos los workers del sistema.

### 2.1. Inicialización

El constructor (`__init__`) recibe:
- `app_settings`: El objeto de configuración del servicio (ej. `EmbeddingServiceSettings`).
- `async_redis_conn`: Una conexión de `redis.asyncio` ya inicializada.

Dentro del constructor, se inicializan componentes clave:
- `self.queue_manager`: Para generar nombres de colas estandarizados.
- `self.redis_client`: Una instancia de `BaseRedisClient` para que el worker pueda actuar como cliente de otros servicios.
- `self.service_name`: Extraído de los `app_settings`.

### 2.2. Flujo de Ejecución

1.  Se llama al método `async def run()`.
2.  `run()` inicia el bucle principal, `_process_action_loop()`.
3.  `_process_action_loop()` escucha indefinidamente en la cola de acciones del servicio (ej. `nooble4:dev:embedding:actions`) usando `BRPOP`.
4.  Cuando llega un mensaje (`DomainAction`), se deserializa y se valida.
5.  Se invoca `await self._handle_action(action)`. **Este es el método que implementa el worker hijo.**
6.  El resultado de `_handle_action` se utiliza para determinar cómo responder:
    - Si la acción era pseudo-síncrona (`action.callback_queue_name` existe) y `_handle_action` devolvió un resultado, se envía una `DomainActionResponse` a la cola de respuesta usando `_send_pseudo_sync_response`.

### 2.3. El Contrato: `_handle_action`

Este es el único método abstracto que un worker hijo **DEBE** implementar.

`async def _handle_action(self, action: DomainAction) -> Optional[dict]:`

- **Responsabilidad**: Contiene la lógica de enrutamiento principal. Debe inspeccionar `action.action_type` y delegar el trabajo a un método privado específico.
- **Retorno**:
    - Para acciones **pseudo-síncronas**, debe devolver un `dict` que será el `data` de la `DomainActionResponse`.
    - Para acciones **asíncronas (fire-and-forget)**, debe devolver `None`.
    - Para manejar errores, debe lanzar una excepción que será capturada por el bucle principal.

## 3. Cómo Implementar un Nuevo Worker

Sigue estos pasos para crear un nuevo worker que cumpla con el estándar.

**Paso 1: Crear la clase y heredar de `BaseWorker`**

```python
# en mi_servicio/workers/mi_worker.py
from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from typing import Optional

class MiWorker(BaseWorker):
    # ...
```

**Paso 2: Implementar `_handle_action`**

Usa una estructura `if/elif/else` para enrutar las acciones a métodos privados.

```python
# dentro de la clase MiWorker
    async def _handle_action(self, action: DomainAction) -> Optional[dict]:
        """
        Ruta la acción al método de manejo apropiado.
        """
        # validated_data = self._validate_action_data(action.data, MiAccionDataModel) # Ejemplo de validación

        if action.action_type == "mi_servicio.accion.hacer_algo":
            return await self._handle_hacer_algo(action.data)
        elif action.action_type == "mi_servicio.accion.notificar":
            await self._handle_notificar(action.data)
            return None # Es fire-and-forget
        else:
            self._logger.warning(f"Acción desconocida recibida: {action.action_type}")
            # Considerar lanzar un error si se reciben acciones inesperadas
            return None
```

**Paso 3: Implementar los métodos de lógica de negocio**

Estos métodos privados contienen la lógica real.

```python
# dentro de la clase MiWorker
    async def _handle_hacer_algo(self, data: dict) -> dict:
        """
        Procesa la acción 'hacer_algo' y devuelve un resultado.
        """
        self._logger.info(f"Procesando 'hacer_algo' con data: {data}")
        # ... lógica de negocio ...
        # Por ejemplo, llamar a otro servicio usando self.redis_client
        # response = await self.redis_client.send_action_pseudo_sync(...)

        result = {"status": "completado", "resultado": 42}
        return result

    async def _handle_notificar(self, data: dict) -> None:
        """
        Procesa una notificación asíncrona.
        """
        self._logger.info(f"Procesando notificación: {data}")
        # ... lógica de negocio que no requiere respuesta ...
```

## 4. Conclusión

La arquitectura `BaseWorker` simplifica el desarrollo de servicios al proporcionar un marco de trabajo robusto y consistente. Al centralizar la lógica de comunicación y establecer un contrato claro (`_handle_action`), permite a los desarrolladores enfocarse en implementar la lógica de negocio de manera clara y explícita.
