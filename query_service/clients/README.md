# Módulo de Clientes (Query Service)

## 1. Propósito General

El módulo `clients` es el responsable de gestionar toda la comunicación entre el `Query Service` y los servicios externos. Su función principal es abstraer la complejidad de las interacciones de red, ya sea con otros microservicios internos (como el `Embedding Service`) o con APIs de terceros (como `Groq` para LLMs y el `Vector Store`).

Al centralizar esta lógica, los `handlers` y `services` del `Query Service` pueden operar a un nivel más alto de abstracción, sin preocuparse por los detalles de implementación de las peticiones HTTP, la comunicación por colas de Redis, el manejo de errores de red, o las políticas de reintentos.

## 2. Patrones y Conexión con `common`

Este módulo sigue un patrón de diseño claro, donde cada cliente es una clase especializada que encapsula la lógica para hablar con un servicio específico. Se apoya fuertemente en las clases base proporcionadas por el módulo `common`, lo cual asegura consistencia y reutilización de código en todo el ecosistema de microservicios:

- **`BaseHTTPClient`**: Clientes como `GroqClient` y `VectorClient` extienden esta clase para heredar una instancia configurada de `httpx.AsyncClient`, logging estandarizado y manejo básico de errores HTTP.
- **`BaseRedisClient`**: El `EmbeddingClient` utiliza una instancia de este cliente para comunicarse de forma asíncrona a través de Redis, enviando `DomainAction` a otros servicios.

## 3. Clientes Implementados

A continuación se detalla cada cliente dentro de este módulo.

### 3.1. `EmbeddingClient`

- **Archivo**: `embedding_client.py`
- **Funcionalidad**: Actúa como intermediario para el `Embedding Service`. Su única responsabilidad es solicitar la conversión de texto a vectores de embeddings.
- **Implementación Técnica**: No realiza peticiones HTTP directas. En su lugar, utiliza un `BaseRedisClient` para publicar `DomainAction` en las colas de Redis correspondientes al `Embedding Service`. Esto desacopla eficazmente ambos servicios.
- **Métodos Clave**:
    - `request_embeddings`: Envía una solicitud asíncrona (fire-and-forget o con callback) para un lote de textos. Es útil para operaciones de ingesta o procesamiento en segundo plano.
    - `request_query_embedding`: Realiza una solicitud pseudo-síncrona para obtener el embedding de una única consulta. Este método es crucial para el flujo RAG, ya que espera activamente la respuesta antes de continuar.
- **Opinión de la Implementación**: La implementación es robusta y sigue un patrón de comunicación entre microservicios bien establecido. La distinción entre métodos asíncronos y pseudo-síncronos es adecuada y cubre los casos de uso necesarios para el servicio. No se observan inconsistencias.

### 3.2. `GroqClient`

- **Archivo**: `groq_client.py`
- **Funcionalidad**: Cliente especializado para interactuar con la API de Groq, que provee los modelos de lenguaje (LLMs) para la generación de respuestas.
- **Implementación Técnica**: Extiende `BaseHTTPClient`. Configura los headers de autenticación (`Bearer Token`) y gestiona las peticiones HTTP a la API de Groq. Implementa una política de reintentos con `tenacity` para manejar errores transitorios (ej. `503 Service Unavailable`), lo cual aumenta la resiliencia del servicio.
- **Métodos Clave**:
    - `generate`: Es el método principal. Construye el payload de la petición con los mensajes, el modelo y los parámetros de generación (temperatura, max_tokens, etc.). Parsea la respuesta JSON para extraer el contenido generado y las métricas de uso de tokens.
    - `list_models`, `health_check`: Métodos de utilidad para verificar la salud del servicio y listar los modelos disponibles.
- **Opinión de la Implementación**: Es un cliente muy bien implementado. La encapsulación de la lógica de la API, el manejo de errores y la política de reintentos son excelentes prácticas. La interfaz que expone es limpia y fácil de usar para los handlers. No se observan inconsistencias.

### 3.3. `VectorClient`

- **Archivo**: `vector_client.py`
- **Funcionalidad**: Cliente diseñado para comunicarse con una base de datos vectorial (Vector Store). Abstrae las operaciones de búsqueda por similitud.
- **Implementación Técnica**: Extiende `BaseHTTPClient`. Está diseñado para ser agnóstico al proveedor específico del Vector Store, asumiendo que este expone una API REST con endpoints predecibles (ej. `/api/v1/search`).
- **Métodos Clave**:
    - `search`: Recibe un embedding, IDs de colecciones y parámetros de búsqueda. Construye la petición y la envía al Vector Store. Luego, parsea la respuesta para convertirla en una lista de objetos `SearchResult` estandarizados.
    - `health_check`: Verifica la disponibilidad del servicio.
- **Opinión de la Implementación e Inconsistencias**:
    
    - **Diseño**: El cliente es una excelente abstracción que aísla al resto del servicio de los detalles del Vector Store. El método `_parse_search_results` asume un formato de respuesta genérico. Si en el futuro se necesitaran soportar múltiples proveedores de bases de datos vectoriales (Qdrant, Pinecone, etc.), este método podría requerir una refactorización (ej. usando un patrón `Adapter`) para manejar las diferencias entre las APIs de cada proveedor. Para un único backend, la implementación actual es adecuada y limpia.
