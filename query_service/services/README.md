# Módulo de Servicios (Query Service)

## 1. Propósito del Módulo

El módulo `services` en el `Query Service` actúa como la **capa de fachada (Facade)** y **orquestación central** para la lógica de negocio. Su principal responsabilidad es recibir solicitudes de alto nivel, encapsuladas como objetos `DomainAction` (del módulo `common`), y despachar estas acciones al `handler` apropiado que se especializa en la tarea específica.

Este diseño desacopla eficazmente al `worker` (responsable de la comunicación con la infraestructura de mensajería como Redis Streams) de los detalles de implementación de la lógica de negocio, que residen en los `handlers`.

## 2. Archivos y Clases Implementadas

Este módulo se centra en un archivo clave:

-   **`query_service.py`**: Define la clase `QueryService`.

### `QueryService` (Clase Principal)

-   **Herencia**: `QueryService` hereda de `common.services.BaseService`, lo que le proporciona una base común de funcionalidades de servicio, incluyendo configuración y logging.
-   **Funcionalidad Central**: Esta clase es el orquestador principal. Durante su inicialización, instancia los `handlers` necesarios (`RAGHandler`, `SearchHandler`).
-   **Inicialización de `EmbeddingClient`**: Notablemente, el `EmbeddingClient` (utilizado para obtener embeddings de texto) se inicializa de forma **condicional**. Solo se crea una instancia si se proporciona un `service_redis_client` al `QueryService`. Esto implica que el servicio puede operar (aunque potencialmente con funcionalidad degradada o de fallback, como se ve en los `handlers`) incluso si la comunicación con un `Embedding Service` externo no está configurada.

#### Método Principal: `process_action(action: DomainAction)`

Este método asíncrono es el corazón del `QueryService` y funciona como un **despachador (dispatcher)**:

1.  **Recepción y Logging**: Recibe un objeto `DomainAction`. Se realiza un logging detallado de la acción entrante, incluyendo `action_id`, `action_type`, `tenant_id`, y `correlation_id` para trazabilidad.
2.  **Enrutamiento por `action.action_type`**: Inspecciona el campo `action.action_type` (ej. `"query.generate"`, `"query.search"`, `"query.status"`).
3.  **Delegación a Métodos Privados**: Basado en el tipo, invoca un método privado específico (`_handle_generate`, `_handle_search`, `_handle_status`) para manejar la acción.
4.  **Manejo de Errores Robusto**:
    -   **`ValidationError`**: Si el `action.data` no se ajusta al modelo Pydantic esperado (ej. `QueryGeneratePayload`), se captura la excepción, se registra el error y se devuelve un `QueryErrorResponse` estructurado.
    -   **`ExternalServiceError`**: Si un handler o cliente encuentra un problema con un servicio externo y lanza esta excepción, `QueryService` la captura y la formatea en un `QueryErrorResponse`.
    -   **`InvalidActionError`**: Se lanza si el `action.action_type` no es soportado.
    -   **Otras Excepciones**: Cualquier otra excepción inesperada se captura, se registra y se **vuelve a lanzar**. Esto permite que una capa superior (probablemente el `BaseWorker`) maneje estos errores de forma genérica, manteniendo la lógica de `QueryService` enfocada.
5.  **Respuesta**: El método devuelve un diccionario que representa el campo `data` de un `DomainActionResponse`, o `None` en ciertos flujos (aunque típicamente se devuelve un diccionario de respuesta o error).

#### Métodos de Manejo Específicos (`_handle_generate`, `_handle_search`)

-   **Parseo de Payload**: Validan y parsean `action.data` usando los modelos Pydantic correspondientes (`QueryGeneratePayload`, `QuerySearchPayload`).
-   **Uso de `action.metadata`**: Extraen configuraciones de `action.metadata`, permitiendo que ciertos parámetros sean sobrescritos dinámicamente en tiempo de ejecución (ej. `top_k`, `llm_model`).
-   **Delegación a Handlers**: Invocan los métodos apropiados en `self.rag_handler` o `self.search_handler`.
-   **Paso de Contexto y Clientes**: Pasan todos los datos relevantes al handler, incluyendo el `query_text`, `collection_ids`, `tenant_id`, `session_id`, `trace_id`, `correlation_id`, `task_id`, y el (posiblemente `None`) `self.embedding_client`.
-   **Formato de Respuesta**: Las respuestas de los handlers (que son modelos Pydantic) se convierten a diccionarios usando `.model_dump()`.

#### Método `_handle_status`

-   Actualmente es un **placeholder** y devuelve un mensaje indicando que la funcionalidad de chequeo de estado no está implementada. Esto está claramente señalado en el código.

## 3. Patrones de Diseño Empleados

-   **Patrón Fachada (Facade)**: `QueryService` simplifica la interfaz para interactuar con el subsistema de procesamiento de consultas (compuesto por varios handlers y clientes). El `worker` no necesita conocer los detalles internos.
-   **Patrón Estrategia (Strategy)**: Implícitamente, los diferentes `handlers` representan estrategias distintas para procesar tipos de consultas. `QueryService` selecciona la estrategia adecuada en tiempo de ejecución.
-   **Inyección de Dependencias**: Los `handlers` y el `service_redis_client` (para el `EmbeddingClient`) se inyectan o se proporcionan durante la inicialización, lo que mejora la modularidad y la capacidad de prueba.

## 4. Conexión e Interacciones con Otros Módulos

-   **`workers`**: El `QueryWorker` (en el módulo `workers`) instancia y utiliza `QueryService` para procesar las `DomainAction` que consume de Redis.
-   **`handlers`**: `QueryService` depende directamente de `RAGHandler` y `SearchHandler` para ejecutar la lógica de negocio principal.
-   **`clients`**: Indirectamente a través de los handlers, y directamente para `EmbeddingClient`.
-   **`models`**: Utiliza intensivamente los modelos de `payloads.py` para la validación de datos de entrada y la estructuración de datos de salida.
-   **`common`**: Depende de manera crucial de:
    -   `common.services.BaseService` (clase base).
    -   `common.models` (para `DomainAction`, `DomainActionResponse`, `ErrorDetail`).
    -   `common.errors.exceptions` (para `InvalidActionError`, `ExternalServiceError`).

## 5. Evaluación de la Implementación

La implementación del `QueryService` es **excepcional** y refleja una arquitectura de software madura y bien estructurada:

-   **Claridad y Cohesión**: La clase tiene una responsabilidad única y bien definida: despachar y orquestar acciones. No se mezcla con la lógica detallada de los handlers.
-   **Robustez**: El manejo de errores es completo y diferenciado, proporcionando respuestas estructuradas para errores esperados y permitiendo que errores inesperados se propaguen a un manejador global.
-   **Extensibilidad**: El diseño es altamente extensible. Añadir soporte para un nuevo `action_type` implicaría:
    1.  Crear un nuevo `Handler` para la nueva lógica.
    2.  Añadir una nueva rama `elif action.action_type == "new.action":` en `process_action`.
    3.  Definir los modelos de payload correspondientes en `models/payloads.py`.
    El impacto en el resto del sistema sería mínimo.
-   **Flexibilidad**: La inicialización condicional del `EmbeddingClient` y el uso de `action.metadata` para overrides de configuración son ejemplos de un diseño flexible.

No se observan inconsistencias o debilidades significativas en este módulo. Es un componente central ejemplar que contribuye a la solidez general del `Query Service`.
