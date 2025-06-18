# Módulo de Modelos (Query Service)

## 1. Propósito General

El módulo `models` es el responsable de definir todos los esquemas de datos y estructuras de información que se utilizan en el `Query Service`. Su función principal es garantizar que los datos que fluyen a través del sistema (tanto en las solicitudes de entrada como en las respuestas de salida) sean válidos, consistentes y fuertemente tipados.

Este módulo utiliza `Pydantic` como base para definir todos los modelos, lo que proporciona validación automática de datos, serialización/deserialización de JSON y una excelente integración con frameworks como FastAPI para la documentación de APIs.

## 2. Patrones y Conexión con `common`

Los modelos de este servicio siguen un patrón de composición y herencia, aprovechando las definiciones base del módulo `common` cuando es aplicable:

- **`common.models`**: Este módulo proporciona modelos de datos transversales a todo el ecosistema, como `DomainAction` y `DomainActionResponse`. Los modelos del `Query Service` se utilizan como el campo `data` dentro de estas acciones de dominio cuando se comunican a través de Redis.
- **`pydantic.BaseModel`**: Todas las clases en `payloads.py` heredan de `BaseModel`, lo que les confiere toda la funcionalidad de Pydantic.

## 3. Archivos y Modelos Implementados

El módulo contiene un archivo principal:

- **`payloads.py`**: Este archivo define todas las estructuras de datos para las operaciones del servicio.

### 3.1. Modelos de Solicitud (Payloads de Entrada)

Estos modelos validan los datos que llegan en las solicitudes al servicio.

- **`QueryGeneratePayload`**: Define el cuerpo esperado para una solicitud a la funcionalidad de RAG (`generate`). Incluye:
    - `query_text`: La pregunta del usuario.
    - `collection_ids`: Las colecciones donde buscar el contexto.
    - Parámetros opcionales para sobreescribir la configuración por defecto del LLM (`model`, `temperature`, `max_tokens`, `top_p`, etc.).
    - `user_id`: Para seguimiento y personalización.

- **`QuerySearchPayload`**: Define el cuerpo para una solicitud de búsqueda vectorial pura (`search`). Es similar a `QueryGeneratePayload` pero sin los parámetros específicos del LLM.

- **`EmbeddingRequest`**: Modelo interno utilizado por el `EmbeddingClient` para solicitar embeddings al `Embedding Service`.

### 3.2. Modelos de Respuesta (Payloads de Salida)

Estos modelos estructuran los datos que el servicio devuelve como respuesta.

- **`SearchResult`**: Representa un único resultado de búsqueda vectorial. Contiene el fragmento de texto (`content`), el score de similitud, y metadatos como el ID del documento y la colección.

- **`QuerySearchResponse`**: La respuesta completa para una operación de búsqueda. Contiene una lista de `SearchResult`, el texto de la consulta original y metadatos sobre la búsqueda (tiempo, colecciones consultadas).

- **`QueryGenerateResponse`**: La respuesta completa para una operación de RAG. Incluye:
    - `response_text`: La respuesta generada por el LLM.
    - `search_results`: La lista de `SearchResult` utilizados como contexto.
    - `token_usage`: Un diccionario con las métricas de uso de tokens del LLM.
    - Metadatos sobre la consulta y la generación.

## 4. Opinión de la Implementación

La implementación de los modelos es **excelente** y sigue las mejores prácticas.

- **Claridad y Especificidad**: Cada operación (`generate`, `search`) tiene sus propios modelos de payload de entrada y salida, lo que hace que la API sea explícita y fácil de entender.
- **Validación Robusta**: El uso de Pydantic con tipos de datos específicos (ej. `List[str]`, `Optional[float]`) y validadores implícitos previene una gran cantidad de errores en tiempo de ejecución.
- **Documentación Automática**: Estos modelos pueden ser utilizados directamente por FastAPI para generar documentación interactiva de la API (Swagger/OpenAPI), lo cual es una ventaja enorme para el desarrollo y la integración.

No se observan inconsistencias ni debilidades en este módulo. Es un pilar fundamental que aporta robustez y claridad al resto del servicio.
