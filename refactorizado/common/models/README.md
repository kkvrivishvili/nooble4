# Módulo de Modelos Comunes (`refactorizado.common.models`)

Este módulo define los modelos de datos Pydantic fundamentales utilizados en toda la plataforma Nooble4. Estos modelos aseguran una estructura de datos coherente para la comunicación entre servicios, el manejo de errores y la representación de contextos de ejecución.

## Archivos Principales y Modelos Exportados

El archivo `__init__.py` de este módulo exporta los siguientes modelos clave:

-   `DomainAction` (de `actions.py`)
-   `DomainActionResponse` (de `actions.py`)
-   `ErrorDetail` (de `actions.py`)
-   `ExecutionContext` (de `execution_context.py`)

### 1. `actions.py`

Este archivo contiene los modelos esenciales para la comunicación basada en acciones:

-   **`ErrorDetail`**: Un modelo estructurado para describir errores. Incluye:
    -   `error_type`: Tipo general del error (ej: 'ValidationError').
    -   `error_code`: Código específico de negocio (ej: 'AGENT_NOT_FOUND').
    -   `message`: Mensaje descriptivo del error.
    -   `details`: Diccionario para información adicional estructurada.

-   **`DomainAction`**: El modelo principal para representar una solicitud o comando en el sistema. Sus campos clave incluyen:
    -   `action_id`: UUID único para la acción.
    -   `action_type`: String que define la acción (formato: "servicio_destino.entidad.verbo").
    -   `timestamp`: Fecha y hora de creación (UTC).
    -   `tenant_id`, `user_id`, `session_id`: Identificadores de contexto de negocio.
    -   `origin_service`: Nombre del servicio que emite la acción.
    -   `correlation_id`: UUID para correlacionar acciones y respuestas en un flujo.
    -   `trace_id`: UUID para el rastreo distribuido a través de múltiples servicios.
    -   `callback_queue_name`, `callback_action_type`: Para patrones de comunicación con callbacks.
    -   `data`: Payload específico de la acción (un diccionario que idealmente se valida con otro modelo Pydantic).
    -   `metadata`: Metadatos adicionales.

-   **`DomainActionResponse`**: El modelo para las respuestas a una `DomainAction`. Contiene:
    -   `action_id`: ID de la `DomainAction` original.
    -   `correlation_id`, `trace_id`: Deben coincidir con los de la `DomainAction` original.
    -   `success`: Booleano que indica si la acción fue exitosa.
    -   `timestamp`: Fecha y hora de creación de la respuesta (UTC).
    -   `data`: Payload de la respuesta si `success` es `True`.
    -   `error`: Objeto `ErrorDetail` si `success` es `False`.
    -   Incluye una validación (`@root_validator`) para asegurar la consistencia entre `success`, `data`, y `error`.

### 2. `execution_context.py`

Define el modelo `ExecutionContext`, utilizado para pasar información de contexto relevante a través de los servicios o dentro de un mismo servicio durante el procesamiento de una solicitud.

-   **`ExecutionContext`**: Representa el contexto en el que se ejecuta una operación. Sus campos incluyen:
    -   `context_id`: Identificador único del contexto (ej: "agent-123").
    -   `context_type`: Tipo de contexto (ej: "agent", "workflow").
    -   `tenant_id`: ID del tenant.
    -   `session_id`: ID de la sesión de conversación (opcional).
    -   `primary_agent_id`: ID del agente principal involucrado.
    -   `agents`: Lista de IDs de todos los agentes involucrados.
    -   `collections`: Lista de IDs de todas las colecciones utilizadas.
    -   `metadata`: Diccionario para metadatos específicos del contexto.
    -   `created_at`: Timestamp de creación.

    **Nota sobre Inconsistencias:** Como se detalla en `refactorizado/common/inconsistencies.md`, este modelo actualmente contiene un campo `tenant_tier` que se considera obsoleto y debería eliminarse para alinearse con la nueva gestión centralizada de tiers.

## Uso

Estos modelos se importan generalmente desde `refactorizado.common.models`:

```python
from refactorizado.common.models import DomainAction, DomainActionResponse, ErrorDetail, ExecutionContext

# Ejemplo de creación de una DomainAction
mi_accion = DomainAction(
    action_type="mi_servicio.entidad.verbo",
    tenant_id="tenant-ejemplo-123",
    data={"parametro1": "valor1"}
)

# Ejemplo de creación de un ExecutionContext
contexto = ExecutionContext(
    context_id="workflow-abc-789",
    context_type="workflow",
    tenant_id="tenant-ejemplo-123",
    primary_agent_id="agent-principal-001",
    agents=["agent-principal-001", "agent-secundario-002"],
    collections=["collection-datos-xyz"]
)
```

Estos modelos son fundamentales para mantener la consistencia y la interoperabilidad entre los diferentes microservicios de Nooble4.
