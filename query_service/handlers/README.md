# Módulo de Handlers (Query Service)

## 1. Propósito del Módulo

El módulo `handlers` es el corazón lógico del `Query Service`. Su responsabilidad principal es orquestar la lógica de negocio para procesar diferentes tipos de solicitudes de consulta. Actúa como una capa de coordinación que utiliza los `clients` para interactuar con servicios externos y los `models` para estructurar los datos. Cada handler se especializa en un flujo de trabajo particular, como la búsqueda vectorial pura o la generación de respuestas aumentadas por recuperación (RAG).

Los handlers son invocados por el `QueryService` (del módulo `services`), que actúa como una fachada, seleccionando y delegando la tarea al handler apropiado según la naturaleza de la solicitud.

## 2. Patrones de Diseño y Conexión con `common`

-   **Especialización por Tarea**: Cada handler (`SearchHandler`, `RAGHandler`) es una clase especializada que encapsula un flujo de procesamiento completo.
-   **Herencia de `BaseHandler`**: Todos los handlers extienden `common.handlers.BaseHandler`. Esta clase base proporciona funcionalidades comunes cruciales:
    -   Acceso a la configuración de la aplicación (`app_settings` de tipo `QueryServiceSettings`).
    -   Una instancia de `logging` configurada (`self._logger`).
    -   Opcionalmente, una conexión directa a Redis (`self.direct_redis_conn`) si se necesita para operaciones que no pasan por `DomainAction` (aunque actualmente no se usa explícitamente en estos handlers para lógica principal).
-   **Inyección de Dependencias**: Los handlers reciben sus dependencias principales (como los `clients` específicos que necesitan) durante la inicialización (`__init__`). Esto promueve el desacoplamiento y facilita las pruebas unitarias al permitir el uso de mocks.
-   **Manejo de Errores**: Los handlers suelen capturar excepciones de los clientes y, si es necesario, las envuelven en excepciones más genéricas como `ExternalServiceError` (de `common.errors.exceptions`) antes de propagarlas hacia arriba.

## 3. Handlers Implementados y Análisis Detallado

### 3.1. `SearchHandler`

-   **Archivo**: `search_handler.py`
-   **Funcionalidad**: Gestiona solicitudes de **búsqueda vectorial pura**. Su propósito es encontrar y devolver los documentos o fragmentos de texto (`chunks`) más relevantes para una consulta dada, sin ninguna capa de generación de lenguaje natural por un LLM. Es ideal para casos de uso como "búsqueda semántica" o "encontrar contenido similar".
-   **Flujo de Trabajo Detallado**:
    1.  Recibe el texto de la consulta (`query_text`), `collection_ids`, `tenant_id`, y otros parámetros de búsqueda (ej. `top_k`, `similarity_threshold`).
    2.  Invoca a `self._get_query_embedding()` para convertir el `query_text` en un vector de embedding. Este método es un punto crítico (ver sección sobre "Fallback de Embedding").
    3.  Utiliza el `VectorClient` (instanciado en `__init__`) para realizar la búsqueda en la base de datos vectorial, pasando el embedding de la consulta y los parámetros relevantes.
    4.  Construye y devuelve un objeto `QuerySearchResponse` que contiene los resultados (`SearchResult`), metadatos de la búsqueda y tiempos.
-   **Dependencias Clave**: `VectorClient`, `EmbeddingClient` (inyectado en el método `search_documents`).

### 3.2. `RAGHandler`

-   **Archivo**: `rag_handler.py`
-   **Funcionalidad**: Orquesta el flujo completo de **Retrieval-Augmented Generation (RAG)**. Su objetivo es generar respuestas coherentes y contextualmente relevantes a preguntas, utilizando un LLM cuya generación está fundamentada en información recuperada de una base de datos vectorial.
-   **Flujo de Trabajo Detallado**:
    1.  **Obtención de Embedding**: Similar al `SearchHandler`, llama a `self._get_query_embedding()` para obtener el vector de embedding de la consulta (punto crítico, ver "Fallback de Embedding").
    2.  **Búsqueda (Retrieval)**: Llama a `self._search_documents()`, que internamente usa el `VectorClient` para recuperar los `chunks` de contexto más relevantes basados en el embedding de la consulta.
    3.  **Construcción del Prompt**: Invoca a `self._build_rag_prompt()`. Este método ensambla un prompt complejo para el LLM, que incluye:
        -   Un prompt de sistema (configurable, con un default en `_get_default_system_prompt()`).
        -   El historial de conversación (si se proporciona, limitado a los últimos mensajes).
        -   El contexto recuperado de los `search_results`, formateado para fácil lectura por el LLM.
        -   La pregunta original del usuario.
    4.  **Generación (Generation)**: Llama a `self._generate_response()`, que utiliza el `GroqClient` para enviar el prompt ensamblado al LLM y obtener la respuesta generada, junto con el uso de tokens.
    5.  **Formateo de Respuesta**: Empaqueta la respuesta generada, los `search_results` (fuentes), y metadatos (modelo LLM, tiempos, tokens) en un objeto `QueryGenerateResponse`.
-   **Dependencias Clave**: `VectorClient`, `GroqClient`, `EmbeddingClient` (inyectado en el método `process_rag_query`).

## 4. Discusión Crítica: El Fallback de Embedding

Una característica de diseño significativa y controversial en ambos handlers es el comportamiento de fallback dentro de sus respectivos métodos `_get_query_embedding()`.

-   **Comportamiento Actual**:
    -   Si se proporciona un `embedding_client` funcional y la llamada a `embedding_client.request_query_embedding()` tiene éxito, se utiliza el embedding real devuelto por el `Embedding Service`.
    -   **Si la llamada al `Embedding Service` falla, o si no se proporciona un `embedding_client` (o faltan `session_id`/`task_id` requeridos por el cliente), ambos handlers recurren a generar un *embedding simulado***:
        -   `SearchHandler`: Genera un embedding determinista basado en el hash MD5 del `query_text`. Esto significa que la misma consulta (sin un `EmbeddingService` funcional) siempre producirá el mismo embedding simulado.
        -   `RAGHandler`: Genera un embedding aleatorio normalizado (no determinista para la misma consulta si el `EmbeddingService` falla repetidamente).

-   **Implicaciones y Riesgos Severos**:
    -   **Resultados Engañosos**: Un embedding simulado (ya sea por hash o aleatorio) **no tiene relación semántica** con el `query_text`. Por lo tanto, la búsqueda vectorial realizada con dicho embedding recuperará documentos que no son relevantes para la consulta del usuario. Esto puede llevar a:
        -   En `SearchHandler`: Devolver resultados de búsqueda incorrectos y sin sentido.
        -   En `RAGHandler`: Generar respuestas de LLM basadas en contexto completamente irrelevante, lo que resulta en información incorrecta, confusa o fabricada.
    -   **Degradación Silenciosa de Calidad**: El sistema puede parecer "funcional" (no lanza errores visibles inmediatamente) pero produce resultados de muy baja calidad, lo que puede erosionar la confianza del usuario.
    -   **Dificultad de Diagnóstico**: Puede ser difícil diagnosticar por qué las búsquedas o respuestas son pobres si no se es consciente de este mecanismo de fallback.

-   **Posibles Justificaciones (Contexto de Desarrollo/Temporal)**:
    -   Este patrón a veces se usa durante el desarrollo temprano para permitir pruebas de flujo de los handlers incluso si el `Embedding Service` no está completamente operativo.
    -   Podría ser una medida temporal para mantener el servicio "en pie" ante fallos del `Embedding Service`, aceptando una degradación severa de la calidad.

-   **Recomendación para Producción (Decisión del USER pendiente)**:
    -   Para un sistema en producción, **este fallback es altamente desaconsejable**. La incapacidad de obtener un embedding real debería tratarse como un error crítico.
    -   La solución ideal sería **eliminar la lógica de generación de embeddings simulados**. Si `_get_query_embedding` no puede obtener un embedding real, debería lanzar una excepción (ej. `ExternalServiceError`), haciendo que el handler falle explícitamente. Esto proporciona un comportamiento más predecible y seguro.

-   **Estado Actual (Según Decisión del USER)**: El USER ha indicado previamente que este comportamiento de fallback debe mantenerse por ahora. Por lo tanto, esta documentación resalta su existencia y sus profundas implicaciones. Es crucial que cualquier usuario o desarrollador del sistema sea consciente de este comportamiento.

## 5. Conclusión sobre el Diseño de Handlers

-   **Fortalezas**: La separación de responsabilidades entre `SearchHandler` y `RAGHandler` es un diseño excelente, permitiendo funcionalidades distintas y claras. La estructura general, el uso de `BaseHandler` y la inyección de dependencias son sólidos.
-   **Debilidad Principal**: El mecanismo de fallback de embedding es el punto más débil y riesgoso del diseño actual de los handlers. Aunque se mantenga por decisión del USER, su impacto en la calidad y fiabilidad de los resultados no puede subestimarse.

La arquitectura de los handlers, excluyendo la cuestión del embedding simulado, es modular, mantenible y sigue buenas prácticas de desarrollo. La resolución o documentación exhaustiva del comportamiento del embedding es clave para la madurez del servicio.
