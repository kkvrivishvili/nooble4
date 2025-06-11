# Estándar de Handlers de Acciones en Nooble4 (Arquitectura v6)

## 1. Filosofía y Principios

Este documento define el estándar para implementar la lógica de negocio en Nooble4. Los principios clave son:

-   **Responsabilidad Única**: Los `Workers` se encargan de la comunicación (escuchar en colas, enviar respuestas). Los `Handlers` se encargan de la lógica de negocio.
-   **Desacoplamiento y Carga Dinámica**: El `BaseWorker` no conoce los `action_types` específicos. Descubre y carga el `Handler` apropiado dinámicamente basado en una convención de nombres.
-   **Contratos de Datos Estrictos**: Los `Handlers` usan modelos Pydantic para validar explícitamente tanto la entrada (`action.data`) como la salida, garantizando la integridad de los datos.
-   **Jerarquía Especializada**: Una jerarquía de clases base (`BaseHandler`, `BaseActionHandler`, `BaseContextHandler`, `BaseCallbackHandler`) proporciona funcionalidades comunes para diferentes patrones de lógica de negocio.
-   **Testeabilidad**: Los `Handlers` son clases aisladas con dependencias explícitas, lo que los hace fáciles de probar unitariamente.

## 2. Arquitectura General y Flujo de Ejecución

1.  Un `BaseWorker` escucha en la cola de acciones de su servicio (ej. `nooble4:dev:management:actions`).
2.  Recibe un mensaje (`DomainAction` en formato JSON) y lo deserializa.
3.  **Dinámicamente**, determina el `Handler` a usar a partir del `action.action_type` (ej. `management.agent.get_config` -> `ManagementAgentGetConfigHandler`).
4.  El `Worker` instancia el `Handler` encontrado, inyectándole las dependencias necesarias (`action`, `redis_pool`, `service_name`).
5.  El `Worker` invoca el método `async def execute()` del `Handler`.
6.  **Dentro de `execute()`**, el propio `Handler` orquesta:
    a.  La validación del `action.data` contra su `action_data_model`.
    b.  La llamada a su método `async def handle()`, que contiene la lógica de negocio pura.
    c.  La validación de la respuesta del `handle()` contra su `response_data_model`.
7.  El `Handler` devuelve el objeto de respuesta (un modelo Pydantic) al `Worker`.
8.  Si la acción era pseudo-síncrona, el `Worker` construye una `DomainActionResponse` con el resultado y la envía a la cola de respuesta especificada.

## 3. La Jerarquía de Handlers

La funcionalidad se organiza en una jerarquía de clases base reutilizables.

### 3.1. `BaseHandler` (La Raíz)

Es la clase más fundamental. Todos los handlers heredan de ella.

-   **Ubicación**: `refactorizado/common/handlers/base_handler.py`
-   **Propósito**: Proporcionar funcionalidades transversales.
-   **Características Clave**:
    -   Recibe `service_name` para un logging contextualizado.
    -   Configura un `logger` estándar para toda la clase.
    -   Define un método `async def initialize()` para lógica de inicialización asíncrona si fuera necesario.

### 3.2. `BaseActionHandler` (Para Lógica Petición-Respuesta)

Hereda de `BaseHandler`. Es el caballo de batalla para la mayoría de las acciones que siguen un patrón simple de petición-respuesta.

-   **Ubicación**: `refactorizado/common/handlers/base_action_handler.py`
-   **Propósito**: Orquestar la validación de entrada/salida y la ejecución de la lógica de negocio.
-   **Contrato que debe implementar el hijo**:
    -   `action_data_model`: Modelo Pydantic para validar `action.data` (o `None` si no hay datos).
    -   `response_data_model`: Modelo Pydantic para validar la salida (o `None` si no hay respuesta).
    -   `async def handle(self, validated_data)`: Método que contiene la lógica de negocio. Devuelve `Optional[BaseModel]`.

#### Ejemplo: `management.agent.get_config`

```python
# refactorizado/agent_management_service/handlers/management/agent/get_config.py
from pydantic import BaseModel, Field
import uuid
from typing import Optional, Type

from refactorizado.common.handlers.base_action_handler import BaseActionHandler

# --- Modelos de Datos ---
class AgentGetConfigData(BaseModel):
    agent_id: uuid.UUID

class AgentGetConfigResponse(BaseModel):
    agent_id: uuid.UUID
    name: str
    version: str

# --- Handler ---
class ManagementAgentGetConfigHandler(BaseActionHandler):

    @property
    def action_data_model(self) -> Type[BaseModel]:
        return AgentGetConfigData

    @property
    def response_data_model(self) -> Type[BaseModel]:
        return AgentGetConfigResponse

    async def handle(self, validated_data: AgentGetConfigData) -> AgentGetConfigResponse:
        self._logger.info(f"Buscando config para agente {validated_data.agent_id}")
        
        # Lógica para buscar la configuración...
        
        # Devolvemos el objeto Pydantic directamente.
        # La validación de salida la hace execute() por nosotros.
        return AgentGetConfigResponse(
            agent_id=validated_data.agent_id,
            name="Agente de Prueba",
            version="2.0.1"
        )
```

### 3.3. `BaseContextHandler` (Para Lógica con Estado)

Hereda de `BaseHandler`. Diseñado para acciones que necesitan leer, modificar y guardar un estado (un "contexto") en Redis.

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
