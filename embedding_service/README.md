# Embedding Service

## 1. Descripción General

El **Embedding Service** es un microservicio asíncrono diseñado para generar embeddings vectoriales para textos. Su principal responsabilidad es recibir solicitudes de texto, interactuar con proveedores de modelos de embedding (como OpenAI) y devolver los vectores de embedding resultantes. Estos embeddings son cruciales para tareas de búsqueda semántica, clustering, y otras aplicaciones de IA.

El servicio está construido en Python (3.9+) utilizando FastAPI para la interfaz HTTP (principalmente para health checks y métricas) y se comunica a través de Redis Streams para el procesamiento de tareas asíncronas, que es donde reside la lógica de negocio principal.

## 2. Arquitectura

El servicio sigue una arquitectura de microservicios limpia y desacoplada, organizada en los siguientes módulos:

- **`main.py` (Punto de Entrada)**: Configura e inicia la aplicación FastAPI. Utiliza el gestor de ciclo de vida (`lifespan`) de FastAPI para inicializar y detener de forma ordenada los recursos críticos, incluyendo el `RedisManager` (para la conexión a Redis) y múltiples instancias de `EmbeddingWorker`.

- **`workers` (`EmbeddingWorker`)**: El motor del servicio. Los `EmbeddingWorker` escuchan constantemente en una cola de Redis (un stream de `DomainAction`). Cuando llega una nueva tarea de embedding, la recogen y la pasan a la capa de servicio (`EmbeddingService`).

- **`services` (`EmbeddingService`)**: Actúa como una fachada. Recibe la `DomainAction` del worker y la delega al handler apropiado según el tipo de acción (`embedding.generate`, `embedding.generate_query`, etc.) y el proveedor de modelo configurado.

- **`handlers`**: Contiene la lógica de negocio principal para interactuar con los proveedores de modelos de embedding.
    - `OpenAIHandler`: Gestiona la comunicación con la API de OpenAI para generar embeddings. Utiliza el SDK oficial de `openai` para Python, incorporando reintentos y manejo de errores específico del SDK.
    - `ValidationHandler`: Proporciona lógica para validar solicitudes de embedding, como la longitud del texto o la disponibilidad del modelo.

- **`clients`**: Abstrae la comunicación con servicios externos.
    - `OpenAIClient`: Un cliente dedicado para interactuar con la API de OpenAI, encapsulando la lógica de llamadas HTTP, autenticación y manejo de reintentos.

- **`models` (`payloads.py`)**: Define todas las estructuras de datos (`payloads` de solicitud y respuesta) utilizando Pydantic, garantizando la validación y consistencia de los datos entre el servicio y sus clientes.

- **`config`**: Gestiona toda la configuración del servicio de manera centralizada y segura, cargando desde variables de entorno y archivos `.env`.

- **`common` (Módulo Externo)**: Proporciona clases base (como `BaseWorker`, `BaseService`, `BaseRedisClient`), modelos (`DomainAction`) y utilidades compartidas entre todos los microservicios.

## 3. Interacción con Otros Microservicios

El `Embedding Service` es típicamente invocado por otros servicios que necesitan convertir texto en embeddings. Ejemplos comunes incluyen:

- **`Ingestion Service`**: Cuando se ingieren nuevos documentos, este servicio puede llamar al `Embedding Service` para obtener los embeddings de los chunks de texto antes de almacenarlos en una base de datos vectorial.
- **`Query Service`**: Cuando se recibe una consulta de usuario, este servicio llama al `Embedding Service` para obtener el embedding de la pregunta, que luego se utiliza para buscar documentos similares en la base de datos vectorial.

La comunicación se realiza mediante la publicación de un objeto `DomainAction` en el stream de Redis del `Embedding Service`.

## 4. Flujo Típico de una Solicitud (`embedding.generate`)

1.  Un servicio cliente (e.g., `Ingestion Service`) necesita generar embeddings para una lista de textos.
2.  El cliente construye un objeto `DomainAction`:
    - `action_type`: `"embedding.generate"`
    - `data`: Un diccionario que cumple con la estructura de `EmbeddingGeneratePayload` (definida en `models/payloads.py`), conteniendo los textos, el modelo deseado (opcional), etc.
    - `callback_queue` y `callback_action_type`: Especificados si el cliente espera una respuesta.
3.  El cliente publica esta `DomainAction` en el stream de Redis del `Embedding Service`.
4.  Uno de los `EmbeddingWorker` consume el mensaje.
5.  El worker pasa la `DomainAction` al `EmbeddingService`.
6.  El `EmbeddingService` identifica el `action_type` y delega la tarea al handler correspondiente (e.g., `OpenAIHandler`).
7.  El `OpenAIHandler` utiliza el `OpenAIClient` para llamar a la API de OpenAI, enviando los textos y parámetros del modelo.
8.  La API de OpenAI devuelve los embeddings.
9.  El handler procesa la respuesta de OpenAI.
10. Si se especificó un callback, el `EmbeddingService` construye un `DomainActionResponse` (conteniendo `EmbeddingResponse` en su campo `data`) y lo publica en la `callback_queue` indicada.

## 5. Cómo Interactuar con Embedding Service (Para Otros Microservicios)

Para que otros microservicios interactúen con el `Embedding Service`, deben enviar mensajes a través de Redis Streams utilizando el objeto `DomainAction`.

### a. El Objeto `DomainAction`

Utilizar la clase `DomainAction` del módulo `common` o una estructura compatible.

- **`action_id` (UUID)**: ID único para la acción.
- **`action_type` (str)**: Tipo de acción. Soportados:
    - `"embedding.generate"`: Genera embeddings para una lista de textos.
    - `"embedding.generate_query"`: Genera embedding para un único texto de consulta (optimizado).
    - `"embedding.batch_process"`: Procesa un lote de textos para embeddings (puede ser usado por `Ingestion Service`).
    - `"embedding.validate"`: Valida textos o la capacidad del modelo.
- **`data` (dict)**: Payload específico de la acción. Ver `models/payloads.py`.
- **`source_service` (str)**: Nombre del servicio solicitante.
- **`target_service` (str)**: Debe ser `"embedding_service"`.
- **`callback_queue` (str, opcional)**: Stream de Redis para la respuesta.
- **`callback_action_type` (str, opcional)**: `action_type` para la respuesta.
- **`tenant_id` (str, opcional)**: Identificador del tenant.
- **`trace_id` (UUID, opcional)**: Para trazabilidad.

### b. Payloads de Solicitud (`data`)

Consultar `embedding_service/models/payloads.py` para las estructuras detalladas:

- **`action_type='embedding.generate'`**: Usar `EmbeddingGeneratePayload`.
    - Campos clave: `texts: List[str]`, `model: Optional[str]`, `dimensions: Optional[int]`, `encoding_format: Optional[str]`, `collection_id: Optional[UUID]`, `chunk_ids: Optional[List[str]]`.
- **`action_type='embedding.generate_query'`**: Usar `EmbeddingGenerateQueryPayload`.
    - Campos clave: `texts: List[str]` (debe contener un solo texto), `model: Optional[str]`.
- **`action_type='embedding.batch_process'`**: Usar `EmbeddingBatchPayload`.
    - Campos clave: `texts: List[str]`, `model: Optional[str]`, `chunk_ids: Optional[List[str]]`, `collection_id: Optional[UUID]`.
- **`action_type='embedding.validate'`**: Usar `EmbeddingValidatePayload`.
    - Campos clave: `texts: List[str]`, `model: Optional[str]`.

### c. Publicación en Redis Streams y Recepción de Respuestas

El mecanismo es idéntico al descrito para el `Query Service`: serializar la `DomainAction` y publicarla en el stream de Redis del `Embedding Service`. Si se proporcionan `callback_queue` y `callback_action_type`, el `Embedding Service` enviará un `DomainActionResponse` a esa cola. El campo `data` de la respuesta contendrá una de las estructuras de respuesta definidas en `models/payloads.py` (e.g., `EmbeddingResponse`, `EmbeddingBatchResponse`, `EmbeddingErrorResponse`).

### Ejemplo Conceptual (Python)

```python
# Asumiendo common.redis.RedisManager y modelos comunes
from common.models import DomainAction
from embedding_service.models.payloads import EmbeddingGeneratePayload # O una versión común
import uuid

async def request_embeddings_from_service(redis_manager, texts_to_embed):
    payload = EmbeddingGeneratePayload(
        texts=texts_to_embed,
        model="text-embedding-3-small" # Ejemplo
    )
    action = DomainAction(
        action_id=uuid.uuid4(),
        action_type="embedding.generate",
        data=payload.model_dump(),
        source_service="my_requesting_service",
        target_service="embedding_service",
        callback_queue="my_requesting_service:responses",
        callback_action_type="embedding.generate.result"
    )
    embedding_service_stream = "embedding_service:actions" # Verificar config
    await redis_manager.publish_action(embedding_service_stream, action)
    # ...lógica para escuchar en la callback_queue...
```

## 6. Configuración Clave (`.env`)

Variables de entorno importantes:

```
# Redis
REDIS_URL=redis://localhost:6379
REDIS_STREAM_EMBEDDING_SERVICE=embedding_service:actions # Stream donde escucha el worker

# Embedding Service
SERVICE_NAME=embedding_service
WORKER_COUNT=2 # Número de workers

# OpenAI Configuration (Ejemplo)
OPENAI_API_KEY="sk-your_openai_api_key"
OPENAI_BASE_URL="https://api.openai.com/v1" # Opcional, si se usa proxy
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=3
OPENAI_DEFAULT_MODEL="text-embedding-ada-002"
# DEFAULT_DIMENSIONS_BY_MODEL='{"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}' (Formato JSON string)
# PREFERRED_DIMENSIONS=1536 (Para modelos que soportan dimensiones variables)
# ENCODING_FORMAT=float # O base64

# Logging
LOG_LEVEL=INFO
```

## 7. Endpoints HTTP

El servicio expone endpoints HTTP a través de FastAPI, principalmente para monitoreo:

- `GET /`: Información básica del servicio.
- `GET /health`: Health check simple.
- `GET /health/detailed`: Health check detallado (verifica Redis, workers, etc.).
- `GET /metrics`: Placeholder para métricas del servicio.
- `GET /docs`: Documentación interactiva de la API (Swagger UI).

## 8. Consideraciones Adicionales

- **Manejo de Errores**: El servicio y sus clientes deben estar preparados para manejar errores, tanto de validación como de comunicación con la API de OpenAI. Las respuestas de error se proporcionan a través de `EmbeddingErrorResponse`.
- **Escalabilidad**: El número de `EmbeddingWorker` puede ajustarse mediante la variable de entorno `WORKER_COUNT` para escalar la capacidad de procesamiento.
- **Modelos Soportados**: La lógica para soportar diferentes modelos o proveedores de embeddings reside principalmente en los handlers. Actualmente, está enfocado en OpenAI.
```
