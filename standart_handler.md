# [OBSOLETO] Estándar de Handlers de Acciones

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
