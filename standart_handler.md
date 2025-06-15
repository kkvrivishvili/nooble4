# Estándar: Componentes de Negocio Especializados (Handlers v4.0)

## 1. El Rol del "Handler" en la Arquitectura v4.0

En la arquitectura v4.0, el concepto de "Handler" ha sido completamente redefinido. **Ya no es una clase que se carga dinámicamente para una acción específica**. Ese patrón ha sido eliminado para favorecer la claridad y la simplicidad.

Ahora, un "Handler" es simplemente una **clase especializada con una responsabilidad de negocio única y bien definida**. Estos componentes son instanciados y utilizados exclusivamente por la **Capa de Servicio** (`BaseService`) para orquestar la lógica de negocio. No tienen conocimiento del `Worker` ni de las colas de Redis.

**Principios Clave de un Componente/Handler v4.0:**

- **Responsabilidad Única**: Un componente hace una sola cosa y la hace bien. Su propósito es encapsular una pieza de lógica de negocio compleja.
- **Especialización**: Su nombre debe reflejar su propósito específico (ej: `ContextHandler`, `CallbackHandler`, `EmbeddingProcessor`).
- **Desacoplamiento**: No conoce a su llamador (la Capa de Servicio). Recibe los datos que necesita, los procesa y devuelve un resultado.
- **Reutilización**: Al ser componentes pequeños y enfocados, pueden ser reutilizados por diferentes métodos de la Capa de Servicio si es necesario.
- **Invocación Explícita**: Son instanciados y llamados explícitamente por la Capa de Servicio. No hay magia ni carga dinámica.

## 2. El Flujo de Trabajo Correcto

El flujo de procesamiento de una acción es siempre el siguiente:

1.  El **`Worker`** (`BaseWorker`) recibe una `DomainAction` desde Redis.
2.  El `Worker` no contiene lógica de negocio. Su única tarea es deserializar la acción y llamar a su método `_handle_action`.
3.  Dentro de `_handle_action`, el `Worker` delega la acción completa a la **`Capa de Servicio`** (`BaseService`).
4.  La **`Capa de Servicio`** es la orquestadora. Contiene los métodos que implementan los casos de uso del dominio (ej: `generate_embedding`, `validate_tier`).
5.  Para implementar un caso de uso, la Capa de Servicio puede instanciar y utilizar uno o más **Componentes de Negocio Especializados (Handlers)** para delegar tareas específicas.

```mermaid
graph TD
    A[Worker (BaseWorker)] -- Llama a _handle_action --> B(Delega a Servicio);
    B -- Llama a método de servicio --> C[Servicio (BaseService)];
    C -- Orquesta y delega --> D{Componentes Especializados};
    D -- 1. --> E[ContextHandler];
    D -- 2. --> F[Processor];
    D -- 3. --> G[CallbackHandler];
```

## 3. Tipos Comunes de Componentes Especializados

Estos son los "Componentes de Negocio" que utiliza la Capa de Servicio. Aunque no hay una regla estricta, se pueden agrupar en las siguientes categorías:

### 3.1. `ContextHandler`

**Propósito**: Encargado de todo lo relacionado con el `ExecutionContext`. Sus responsabilidades incluyen:
- Cargar datos adicionales para enriquecer el contexto (ej: configuraciones del tenant).
- Validar que el contexto es válido para la operación solicitada.
- Validar permisos y límites basados en el `tenant_tier` y otros datos del contexto.

**Ejemplo (`embedding_service`):**
```python
# embedding_service/handlers/context_handler.py

class EmbeddingContextHandler:
    async def resolve_embedding_context(self, exec_context: ExecutionContext) -> EnrichedContext:
        # ... Lógica para cargar configuraciones del tenant, etc.
        pass

    async def validate_embedding_permissions(self, context: EnrichedContext, ...):
        # ... Lógica para verificar si el tier del tenant permite usar el modelo, etc.
        pass
```

### 3.2. `CallbackHandler`

**Propósito**: Encapsula la lógica de construir y enviar una `DomainAction` de callback. Esto mantiene a la Capa de Servicio limpia de los detalles de la comunicación asíncrona entre servicios.

**Ejemplo (`embedding_service`):**
```python
# embedding_service/handlers/embedding_callback_handler.py

class EmbeddingCallbackHandler:
    def __init__(self, queue_manager: DomainQueueManager, redis_client):
        # ...
    
    async def send_success_callback(self, task_id: str, callback_queue: str, ...):
        # 1. Construir el payload del callback (EmbeddingCallbackAction).
        # 2. Crear la DomainAction de callback.
        # 3. Usar el redis_client para enviarla a la callback_queue.
        pass
```

### 3.3. Otros Componentes (Processors, Validators, etc.)

Aunque no siempre lleven el sufijo "Handler", otras clases especializadas como `EmbeddingProcessor` o `TierValidationService` siguen la misma filosofía. Son componentes con una responsabilidad única que son orquestados por la Capa de Servicio para ejecutar la lógica de negocio principal.

## 4. Conclusión

En la arquitectura v4.0, los **Handlers ya no existen como un patrón de carga dinámica**. Han sido reemplazados por un flujo explícito y claro: **Worker -> Servicio -> Componentes**.

Este enfoque promueve un código más limpio, modular, explícito y fácil de probar, donde cada clase tiene un propósito claro y definido.
