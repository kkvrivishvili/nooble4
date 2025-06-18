# Módulo de Modelos (Query Service)

## 1. Propósito del Módulo

El módulo `models` es fundamental para el `Query Service`, ya que define todos los esquemas de datos y estructuras de información utilizados. Su función principal es asegurar que los datos que fluyen a través del servicio —tanto en solicitudes de entrada como en respuestas de salida— sean válidos, consistentes y fuertemente tipados. Esto es crucial para la fiabilidad y mantenibilidad del servicio.

Todos los modelos se definen utilizando `Pydantic`, una biblioteca de Python para validación de datos y gestión de configuraciones. Esto proporciona:

-   **Validación Automática de Datos**: Los tipos y restricciones se verifican en tiempo de ejecución.
-   **Serialización/Deserialización**: Fácil conversión desde y hacia JSON.
-   **Documentación de API**: Excelente integración con FastAPI para generar automáticamente esquemas OpenAPI (Swagger UI).

## 2. Patrones de Diseño y Conexión con `common`

-   **Herencia de `pydantic.BaseModel`**: Todas las clases de modelos de datos en `payloads.py` heredan de `BaseModel`, obteniendo así todas las funcionalidades de Pydantic.
-   **Composición con `common.models`**: Los modelos definidos en `query_service.models` están diseñados para ser utilizados como el campo `data` dentro de los modelos `DomainAction` y `DomainActionResponse` del módulo `common.models`. Esta es la forma estándar en que los servicios se comunican asíncronamente a través de Redis Streams en esta arquitectura: una `DomainAction` encapsula una `action_type` (ej. `query.generate`) y un `data` (ej. una instancia de `QueryGeneratePayload`).
-   **Uso de `Field` y Validadores**: Se utiliza `Field` de Pydantic para añadir metadatos descriptivos, valores por defecto y restricciones (ej. `ge`, `le`) a los campos del modelo. Además, se emplean `@field_validator` para lógica de validación personalizada más compleja (ej. asegurar que `collection_ids` no esté vacío).

## 3. Archivos y Modelos Implementados

El módulo se centra principalmente en el archivo `payloads.py`, que contiene las siguientes categorías de modelos:

### 3.1. Modelos de Solicitud (Payloads de Entrada)

Estos modelos validan los datos que llegan en las solicitudes al servicio, típicamente como el contenido del campo `data` de una `DomainAction`.

-   **`QueryGeneratePayload`**: Define la estructura para una solicitud de RAG (`query.generate`). Es un modelo muy completo que incluye:
    -   Campos obligatorios: `query_text` (pregunta del usuario), `collection_ids` (dónde buscar).
    -   Parámetros de búsqueda opcionales: `top_k`, `similarity_threshold`.
    -   Parámetros de generación de LLM opcionales: `llm_model`, `temperature`, `max_tokens`, `system_prompt`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop_sequences`.
    -   Contexto adicional: `user_id`, `conversation_history` (lista de dicts), `response_mode`.
    -   *Fortaleza*: Su exhaustividad permite una gran flexibilidad y control fino sobre el proceso RAG.

-   **`QuerySearchPayload`**: Define la estructura para una solicitud de búsqueda vectorial pura (`query.search`). Incluye `query_text`, `collection_ids`, y parámetros de búsqueda como `top_k`, `similarity_threshold`, y `filters` (un dict para filtros de metadatos).

-   **`QueryStatusPayload`**: Para consultar el estado de una consulta, esperando un `query_id`.

### 3.2. Modelos de Respuesta (Payloads de Salida)

Estos modelos estructuran los datos que el servicio devuelve, usualmente como el campo `data` de una `DomainActionResponse`.

-   **`SearchResult`**: Representa un único fragmento (`chunk`) recuperado de la búsqueda vectorial. Contiene:
    -   `chunk_id`, `content` (texto del chunk), `similarity_score`.
    -   Metadatos del origen: `document_id`, `document_title`, `collection_id`.
    -   Un campo genérico `metadata` (dict) para información adicional.
    -   *Fortaleza*: Es un modelo bien estructurado que proporciona toda la información necesaria sobre cada pieza de evidencia recuperada.

-   **`QuerySearchResponse`**: Respuesta para una operación de búsqueda. Incluye:
    -   `query_id`, `query_text` original.
    -   `search_results` (lista de `SearchResult`), `total_results`.
    -   `search_time_ms`, `collections_searched`, `timestamp`.

-   **`QueryGenerateResponse`**: Respuesta para una operación RAG. Incluye:
    -   `query_id`, `query_text` original.
    -   `generated_response` (texto del LLM).
    -   `search_results` (lista de `SearchResult` usados como contexto).
    -   Metadatos de generación: `llm_model`, `temperature`, uso de tokens (`prompt_tokens`, `completion_tokens`, `total_tokens`).
    -   Tiempos: `search_time_ms`, `generation_time_ms`, `total_time_ms`.
    -   `timestamp`.

-   **`QueryErrorResponse`**: Modelo estandarizado para respuestas de error. Contiene `query_id` (opcional), `error_type`, `error_message`, `error_details` (opcional) y `timestamp`. Esto es vital para un manejo de errores consistente y depurable.

### 3.3. Modelos Internos / Inter-servicio

-   **`EmbeddingRequest`**: Usado por el `EmbeddingClient` para solicitar embeddings al `Embedding Service`. Contiene `texts` (lista de strings) y un `model` opcional.
-   **`CollectionConfig`**: Define la estructura para la configuración de una colección (ej. `collection_id`, `embedding_model`, `chunk_size`). Útil si el `Query Service` necesita estar al tanto de estos detalles.

## 4. Evaluación de la Implementación

La implementación de los modelos en `payloads.py` es **excepcional** y sigue las mejores prácticas de la industria:

-   **Claridad y Especificidad**: Cada operación tiene modelos de entrada y salida claramente definidos y específicos, lo que hace que la interfaz del servicio (ya sea a través de API HTTP o acciones de dominio) sea explícita y fácil de entender.
-   **Validación Robusta**: El uso intensivo de tipos de Python, `Optional`, y las capacidades de validación de Pydantic (incluyendo `Field` con restricciones y validadores personalizados) previene una gran cantidad de errores de datos en tiempo de ejecución.
-   **Auto-documentación**: Las descripciones en `Field` hacen que los modelos sean auto-documentados. Esto, combinado con FastAPI, puede generar documentación interactiva de API (Swagger/OpenAPI) de alta calidad con mínimo esfuerzo adicional.
-   **Completitud**: Los modelos capturan una gran cantidad de información relevante para cada operación, incluyendo metadatos, información de temporización y detalles de configuración, lo que es valioso para la observabilidad y el análisis.

No se identifican debilidades o inconsistencias significativas en este módulo. Es un pilar fundamental que aporta robustez, claridad y fiabilidad al `Query Service`.
