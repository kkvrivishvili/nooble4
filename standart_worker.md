# Estándar de Workers en Nooble4 (Arquitectura v4.0)

## 1. Filosofía y Principios

La arquitectura de workers v4.0 se basa en el principio de **separación de responsabilidades**. El worker es un componente de **infraestructura**, no de negocio. Su única responsabilidad es actuar como el punto de entrada para las `DomainAction` que llegan desde las colas de Redis y orquestar la respuesta, delegando toda la lógica de negocio a una **Capa de Servicio**.

**Responsabilidades Clave del Worker:**

- **Escuchar Colas Redis**: Monitorea las colas de acciones (`actions`) asignadas a su dominio.
- **Deserializar Acciones**: Convierte el JSON de la cola en un objeto `DomainAction` Pydantic.
- **Delegar Procesamiento**: Pasa la `DomainAction` a la Capa de Servicio a través de un único método: `_handle_action`.
- **Manejar Respuestas y Callbacks**: Recibe el resultado de la Capa de Servicio y, si es necesario, envía una respuesta (pseudo-síncrona) o un callback (asíncrono) a la cola correspondiente.
- **Gestión del Ciclo de Vida**: Maneja su propia inicialización (`initialize`), arranque (`start`) y detención (`stop`).

**Lo que un Worker NO debe hacer:**

- Contener lógica de negocio (validaciones de dominio, acceso a bases de datos, llamadas a APIs externas).
- Conocer los detalles internos de cómo se procesa una acción.
- Registrar múltiples funciones `handler` para diferentes acciones. Este patrón está obsoleto.

## 2. Implementación: `BaseWorker`

Todos los workers deben heredar de `common.workers.base_worker.BaseWorker`.

### 2.1. El Método `_handle_action`

Este es el corazón del patrón v4.0. Es un método abstracto en `BaseWorker` que **debe ser implementado** por cada worker hijo. Actúa como un **enrutador central**.

```python
# Ejemplo en EmbeddingWorker

async def _handle_action(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
    """
    Procesa acciones de dominio centralizadamente.
    """
    if not self.initialized:
        await self.initialize()
        
    action_type = action.action_type
    
    try:
        # Delega a la capa de servicio según el tipo de acción
        if action_type == "embedding.generate":
            return await self.generation_service.generate_embeddings(action)

        elif action_type == "embedding.validate":
            return await self.generation_service.validate_embeddings(action)
            
        else:
            raise ValueError(f"Acción no soportada: {action_type}")
            
    except Exception as e:
        logger.error(f"Error procesando acción {action_type}: {str(e)}")
        # Devuelve un resultado de error estandarizado
        return {
            "success": False,
            "error": str(e)
        }
```

### 2.2. Inicialización de Componentes

El worker es responsable de instanciar la Capa de Servicio y cualquier otro componente que necesite (como handlers de callbacks). Esto se hace típicamente en un método `_initialize_components` que es llamado por `initialize`.

```python
# Ejemplo en EmbeddingWorker

async def _initialize_components(self):
    """Inicializa todos los componentes necesarios."""
    # Instancia el handler de contexto
    self.context_handler = await get_embedding_context_handler(self.redis_client)
    
    # Instancia el handler de callbacks
    self.embedding_callback_handler = EmbeddingCallbackHandler(
        self.queue_manager, self.redis_client
    )
    
    # Instancia la capa de servicio y le inyecta sus dependencias
    self.generation_service = GenerationService(
        self.context_handler, self.redis_client
    )
    
    logger.info("EmbeddingWorker: Componentes inicializados")
```

## 3. Flujo de Vida de una Acción

1.  Un mensaje JSON llega a una cola de acciones de Redis.
2.  El `_process_action_loop` del `BaseWorker` lo recoge.
3.  El worker lo deserializa en un objeto `DomainAction`.
4.  El worker invoca su propia implementación de `_handle_action`, pasándole la acción.
5.  `_handle_action` determina el tipo de acción y llama al método correspondiente en la **Capa de Servicio**.
6.  La Capa de Servicio ejecuta toda la lógica de negocio.
7.  La Capa de Servicio devuelve un diccionario con el resultado (`{"success": True, "result": ...}` o `{"success": False, "error": ...}`).
8.  El `BaseWorker` recibe este diccionario y, si la `DomainAction` original tenía un `callback_queue_name` y un `callback_action_type`, se encarga de enviar el callback correspondiente.
9.  Para respuestas pseudo-síncronas, es responsabilidad del worker (o de la capa de servicio, según el diseño) enviar directamente la `DomainActionResponse` a la cola de respuesta.

Este patrón asegura un desacoplamiento claro, mejora la testeabilidad y centraliza la lógica de enrutamiento, haciendo el sistema más robusto y fácil de mantener.

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
- **Servicios de Negocio**: Instancia y gestiona el ciclo de vida de los servicios de negocio necesarios para procesar las tareas. Estos servicios contienen la lógica de aplicación específica. Este Service deberá ser una implementación que herede de `common.services.BaseService`, asegurando así la conformidad con el contrato de la capa de servicio.

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
