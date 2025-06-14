# Estándar: Handlers Especializados (Arquitectura v4.0)

## 1. El Nuevo Rol del Handler

En la arquitectura v4.0, el concepto de "Handler" ha sido redefinido. Ya no es una función genérica que se registra para un tipo de acción, sino una **clase especializada con una responsabilidad única y bien definida**.

Los Handlers son **componentes de negocio** que son instanciados y utilizados por la **Capa de Servicio** para delegar tareas específicas. No tienen conocimiento del `Worker` ni de las colas de Redis.

**Principios Clave de un Handler:**

- **Responsabilidad Única**: Un handler hace una sola cosa y la hace bien.
- **Especialización**: Su nombre debe reflejar su propósito específico (ej: `ContextHandler`, `CallbackHandler`).
- **Desacoplamiento**: No conoce a su llamador (la Capa de Servicio). Recibe los datos que necesita, los procesa y devuelve un resultado.
- **Reutilización**: Al ser componentes pequeños y enfocados, pueden ser reutilizados por diferentes métodos de la Capa de Servicio si es necesario.

## 2. Tipos Comunes de Handlers

Estos son los "Componentes de Negocio Especializados" que utiliza la Capa de Servicio. Aunque no hay una regla estricta, se pueden agrupar en las siguientes categorías:

### 2.1. `ContextHandler`

**Propósito**: Encargado de todo lo relacionado con el `ExecutionContext`. Sus responsabilidades incluyen:
- Cargar datos adicionales para enriquecer el contexto.
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

### 2.2. `CallbackHandler`

**Propósito**: Encapsula la lógica de construir y enviar una `DomainAction` de callback. Esto mantiene a la Capa de Servicio limpia de los detalles de la comunicación asíncrona.

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

### 2.3. Otros Componentes (Processors, Validators)

Aunque no siempre lleven el sufijo "Handler", otras clases especializadas como `EmbeddingProcessor` o `ValidationService` siguen la misma filosofía. Son componentes con una responsabilidad única que son orquestados por la Capa de Servicio.

## 3. Conclusión

En resumen, el patrón es:

- El **Worker** delega a la **Capa de Servicio**.
- La **Capa de Servicio** orquesta el flujo de trabajo delegando tareas específicas a diferentes **Handlers Especializados**.

Este enfoque promueve un código más limpio, modular y fácil de probar, donde cada clase tiene un propósito claro y definido.

> **ESTE DOCUMENTO ESTÁ OBSOLETO Y SE MANTIENE ÚNICAMENTE COMO REFERENCIA HISTÓRICA.**
> **NO DEBE USARSE COMO GUÍA PARA NUEVAS IMPLEMENTACIONES.**

## Razón de la Obsolescencia

La arquitectura basada en `Handlers` dinámicos ha sido **reemplazada** por el patrón `BaseWorker` unificado. La nueva arquitectura elimina la necesidad de clases `Handler` individuales y la carga dinámica en tiempo de ejecución.

## El Nuevo Estándar: `BaseWorker`

La lógica de negocio que antes residía en los `Handlers` ahora se implementa directamente dentro de los métodos de los workers que heredan de `BaseWorker`.

El enrutamiento de acciones se realiza de forma explícita dentro del método `_handle_action(self, action: DomainAction)` del worker, típicamente usando una estructura `if/elif/else` sobre el `action.action_type`.

**Para entender la arquitectura actual y cómo implementar la lógica de negocio, por favor, consulte el siguiente documento:**

### **[Referencia Principal: Estándar de Workers (`standart_worker.md`)](./standart_worker.md)**

-   **Ubicación**: `refactorizado/common/handlers/base_context_handler.py`
-   **Propósito**: Abstraer el ciclo `GET -> MODIFY -> SET` de un objeto de estado en Redis.
-   **Contrato que debe implementar el hijo**:
    -   `context_model`: Modelo Pydantic que representa el objeto de estado en Redis.
    -   `async def get_context_key(self) -> str`: Devuelve la clave de Redis donde se guarda el contexto.
    -   `async def handle(self, context, validated_data)`: Recibe el contexto cargado desde Redis y los datos de la acción. Devuelve una tupla: `(updated_context, response_object)`.

#### Ejemplo Conceptual: `conversation.message.post`

```python
# --- Handler de Contexto ---
class ConversationMessagePostHandler(BaseContextHandler):
    # ... (action_data_model, response_data_model, context_model) ...

    async def get_context_key(self) -> str:
        # El contexto se guarda por sesión
        return f"context:session:{self.action.session_id}"

    async def handle(self, context: ConversationHistory, validated_data: PostMessageData) -> Tuple[ConversationHistory, PostMessageResponse]:
        # 1. Lógica de negocio
        new_message = f"{validated_data.user}: {validated_data.text}"
        context.messages.append(new_message)
        
        # 2. Generar respuesta
        response = PostMessageResponse(status="ok", message_count=len(context.messages))
        
        # 3. Devolver contexto actualizado y respuesta
        return context, response
```

### 3.4. `BaseCallbackHandler` (Para Enviar Callbacks)

Hereda de `BaseActionHandler`. Es una especialización que añade una utilidad para enviar acciones de callback a otros servicios.

-   **Ubicación**: `refactorizado/common/handlers/base_callback_handler.py`
-   **Propósito**: Estandarizar el envío de acciones de seguimiento (callbacks) de forma asíncrona.
-   **Características Clave**:
    -   Proporciona un método `async def send_callback(...)` que simplifica la creación y envío de una `DomainAction` a una cola de callback, propagando correctamente los IDs (`trace_id`, `session_id`, etc.).

## 4. ¿Qué Handler Usar?

-   **¿Tu lógica es una simple petición-respuesta sin estado?** -> Usa `BaseActionHandler`.
-   **¿Necesitas leer un objeto de Redis, modificarlo y guardarlo?** -> Usa `BaseContextHandler`.
-   **¿Tu handler, como parte de su lógica, necesita disparar una nueva acción asíncrona en otro servicio?** -> Usa `BaseCallbackHandler`.

## 5. Convenciones de Nomenclatura y Ubicación

-   **Ubicación de Handlers**: `refactorizado/<nombre_servicio>/handlers/<dominio>/<recurso>/<verbo>.py`
-   **Nombre de Archivo**: `action_type_in_snake_case.py` (ej. `management_agent_get_config.py`).
-   **Nombre de Clase**: `ActionTypeInPascalCaseHandler` (ej. `ManagementAgentGetConfigHandler`).
