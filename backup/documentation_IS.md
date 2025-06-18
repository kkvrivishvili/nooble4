
## 1. Objetivo del Servicio

El Servicio de Ingestión es responsable de recibir documentos, URLs o texto plano, procesarlos, extraer su contenido, dividirlos en fragmentos (chunks), solicitar la generación de embeddings para estos fragmentos y, finalmente  almacenarlos en una base de datos vectorial Qdrant local para su posterior búsqueda y recuperación. Proporciona actualizaciones en tiempo real del estado del procesamiento a través de WebSockets al front end.

## 2. Arquitectura y Componentes Principales

El servicio está construido con Python, FastAPI para la API REST y WebSockets, y Redis para la gestión de colas y el estado temporal de las tareas. Utiliza LlamaIndex para la extracción de texto y el chunking. Usa una estructura Domain Action, con archivos base en la carpeta common. Se comunica con los otros servicios a traves de Redis Streams, toda esa base esta disponible en los archivos common.

### 2.1. Entrypoint (`main.py`)

- **Aplicación FastAPI**: Inicializa la aplicación FastAPI, configura CORS, routers y manejadores de errores globales.
- **Middleware**: `CORSMiddleware` para permitir orígenes configurados.
- **Manejo de Errores**: Captura `ServiceError` y excepciones generales, devolviendo respuestas JSON estandarizadas.
- **Routers**: Incluye routers de `documents.py`, `tasks.py` y `websockets.py`.
- **Health Check (`/health`)**: Verifica la conexión a Redis (`queue_service`) y el estado del worker.
- **Eventos de Startup/Shutdown**:
    - `startup_event`: Inicializa `queue_service` y arranca el `worker_pool` (si `AUTO_START_WORKERS` es true).
    - `shutdown_event`: Detiene el `worker_pool` y cierra las conexiones de `queue_service`.

### 2.2. Workers



### 2.3. Handlers

Los `handlers` sirven como apoyo a funciones estandarizadas para el manejo de logica core centralizada en la carpeta services del servicio. Adoptan las clase base del archivo base en common.


### 2.4. Servicios Internos

- **`ChunkingService` (`services/chunking.py`)**:
    - **Extracción de Texto**: Utiliza LlamaIndex (`PDFReader`, `DocxReader`, etc.) y un `CustomHTMLReader` (basado en BeautifulSoup) para extraer texto de diversos formatos de archivo.
    - **Validación de Archivos (`validate_file`)**: Verifica tipo MIME, tamaño máximo (`settings.MAX_FILE_SIZE`).
    - **Fragmentación (`split_text_into_chunks`, `split_document_intelligently`)**: Utiliza `llama_index.core.node_parser.SentenceSplitter` con `tiktoken` (modelo `gpt-4`) para dividir el texto en chunks semánticos. Limita el número de chunks a `settings.MAX_CHUNKS_PER_DOCUMENT`.
- **`QueueService` (`services/queue.py`)**:
    - Gestiona la comunicación con Redis para colas y metadatos de tareas.
    - **Métodos Principales**:
        - `enqueue()`: Añade una `DomainAction` a una cola Redis y guarda metadatos de la tarea (estado "pending", timestamps) en un hash Redis (`prefix:meta:{task_id}`).
        - `dequeue()` / `dequeue_as_type()`: Extrae acciones de la cola (bloqueante con `BLPOP`), actualiza el estado de la tarea a "processing".
        - `get_task_status()`: Recupera los metadatos de una tarea desde Redis.
        - `set_task_completed()` / `set_task_failed()`: Actualiza el estado y resultado/error de la tarea en Redis.
        - `acquire_lock()` / `release_lock()`: Implementación de locks distribuidos básicos.

### 2.5. Clientes

- **`EmbeddingClient` (`clients/embedding_client.py`)**:
    - Envía solicitudes HTTP POST (esperando un `202 Accepted`) al Embedding Service (`/api/v1/embeddings/generate`) para generar embeddings para los chunks. La acción enviada es `EmbeddingRequestAction`.
- **`VectorStoreClient` (`clients/vector_store_client.py`)**:
    - **PLACEHOLDER**: Define una interfaz abstracta (`VectorDocument` model) para interactuar con una base de datos vectorial.
    - Métodos como `add_documents()`, `delete_documents()`, `search()` están definidos pero no implementados.
    - La lógica de almacenamiento real en un Vector Store es un **TODO**.

### 2.6. Modelos de Datos

- **`models/actions.py`**: Define las `DomainAction` específicas del servicio:
    - `DocumentProcessAction`: Acción principal para iniciar la ingestión de un documento, URL o texto.
    - `DocumentChunkAction`: (No parece usarse directamente por el worker principal, pero está definida).
    - `EmbeddingRequestAction`: Enviada al Embedding Service.
    - `EmbeddingCallbackAction`: Recibida del Embedding Service.
    - `TaskStatusAction`, `TaskCancelAction`: Para gestión de tareas.
- **`models/tasks.py`**: Define la estructura de las tareas y su estado:
    - `TaskStatus`: Enum (PENDING, PROCESSING, EXTRACTING, CHUNKING, EMBEDDING, STORING, COMPLETED, FAILED, CANCELLED).
    - `TaskType`, `TaskSource`: Enums para categorizar tareas.
    - `TaskProgress`: Modelo para el progreso detallado.
    - `Task`: Modelo Pydantic principal que representa una tarea de ingestión, devuelto por la API.
- **`models/events.py`**: Define los modelos para eventos WebSocket:
    - `EventType`: Enum para diferentes tipos de eventos (PROGRESS_UPDATED, TASK_COMPLETED, ERROR, etc.).
    - `WebSocketEvent`: Modelo base para todos los eventos.
    - `TaskProgressEvent`, `TaskStatusEvent`, `ErrorEvent`, `ProcessingMilestoneEvent`: Modelos específicos para diferentes tipos de notificaciones.

### 2.7. Rutas API

- **`routes/documents.py`**: Endpoints para iniciar la ingestión.
    - `POST /api/v1/documents/`: Endpoint principal para subir archivos, URLs o texto. Crea `DocumentProcessAction` y la encola. Devuelve un objeto `Task` con `task_id`.
    - `POST /api/v1/documents/text`, `POST /api/v1/documents/url`: Endpoints alternativos para texto y URL con payload JSON.
- **`routes/tasks.py`**: Endpoints para gestionar tareas.
    - `GET /api/v1/tasks/{task_id}`: Consulta el estado de una tarea (obtenido de `queue_service.get_task_status()`).
    - `DELETE /api/v1/tasks/{task_id}`: Solicita la cancelación de una tarea (encola `TaskCancelAction`).
    - `GET /api/v1/tasks/`: Lista tareas (actualmente un placeholder, devuelve lista vacía).
- **`routes/websockets.py`**: Endpoint para conexiones WebSocket.
    - `WS /ws/tasks/{task_id}`: Permite a los clientes conectarse para recibir actualizaciones en tiempo real para una tarea específica. Requiere `tenant_id` y `token` (autenticación TODO).
    - Utiliza `ConnectionManager` y `EventDispatcher`.

### 2.8. Configuración (`config/settings.py`)

- Define configuraciones como:
    - Conexión a Redis (`REDIS_HOST`, `REDIS_PORT`, etc.).
    - Nombres de colas (`DOCUMENT_QUEUE`, `EMBEDDING_CALLBACK_QUEUE`, `TASK_STATUS_QUEUE`, `INGESTION_ACTIONS_QUEUE`).
    - Parámetros de chunking (`DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP`, `MAX_CHUNKS_PER_DOCUMENT`).
    - Límites (`MAX_FILE_SIZE`, `MAX_TEXT_LENGTH_PER_DOCUMENT`).
    - URLs de servicios externos (`EMBEDDING_SERVICE_URL`).
    - Configuración de workers (`WORKER_COUNT`, `AUTO_START_WORKERS`).
    - `JOB_TIMEOUT` para la expiración de metadatos de tareas en Redis.

## 3. Flujo de Comunicación y Patrones

1.  **Solicitud de Ingestión (API REST)**:
    - El cliente envía una solicitud a `POST /api/v1/documents/` (o `/text`, `/url`) con los datos del documento, `tenant_id`, `collection_id`, `document_id` y otros metadatos.
    - El servicio valida la solicitud, genera un `task_id` único.
    - Crea una `DocumentProcessAction` y la encola en `settings.DOCUMENT_QUEUE` usando `queue_service`.
    - Responde inmediatamente al cliente con el `task_id` y el estado inicial de la tarea (`PENDING`).
2.  **Conexión WebSocket**:
    - El cliente utiliza el `task_id` para para establecer una tarea con el `IngestionService`.A su vez un `session_id` para una conexión WebSocket a `WS /ws/tasks/{task_id}`.
    - `ConnectionManager` gestiona estas conexiones.
3.  **Procesamiento Asíncrono por `IngestionWorker`**:
    - Un `IngestionWorker` toma la `DocumentProcessAction` de la cola.
    - **Extracción y Chunking**: Si es un archivo, se extrae el texto. El texto se divide en chunks usando `ChunkingService`.
    - **Solicitud de Embeddings**: El worker construye una `EmbeddingRequestAction` (conteniendo los chunks, `task_id`, y `callback_queue_name` = `settings.EMBEDDING_CALLBACK_QUEUE`) y la envía al Embedding Service a través de `EmbeddingClient` (HTTP POST, espera 202).
    - Durante estos pasos, el worker envía actualizaciones de progreso y milestones (`document_received`, `text_extracted`, `chunking_completed`, `embedding_started`) a los clientes WebSocket suscritos a través de `EventDispatcher`.
4.  **Callback del Embedding Service**:
    - El Embedding Service, una vez procesada la solicitud, envía una `EmbeddingCallbackAction` a la `settings.EMBEDDING_CALLBACK_QUEUE` especificada por el Ingestion Service.
    - El `IngestionWorker` (que también escucha esta cola) recibe el callback.
5.  **Almacenamiento y Finalización**:
    - Si el callback es exitoso, el worker prepara los `VectorDocument` (chunks + embeddings).
    - Intenta guardar estos documentos usando `vector_store_client.add_documents()` (actualmente un placeholder).
    - Envía milestones (`embedding_completed`, `storage_completed`) y el estado final (`TaskStatus.COMPLETED` o `TaskStatus.FAILED`) vía WebSocket.
    - Actualiza el estado de la tarea en Redis (`queue_service.set_task_completed` o `set_task_failed`).
    - Envía una `CollectionIngestionStatusAction` (destino y propósito exacto por definir).
6.  **Consulta de Estado (API REST)**:
    - El cliente puede consultar el estado de la tarea en cualquier momento usando `GET /api/v1/tasks/{task_id}`.

## 4. Integración con Otros Servicios

- **Embedding Service**: Solicita la generación de embeddings para los chunks de texto. La comunicación es pseudoasíncrona.
- **Vector Store Qdrant**: El servicio está diseñado para almacenar los chunks y sus embeddings en una base de datos vectorial, pero el cliente 
- **(Potencial) Agent Orchestrator Service**: E
- **Redis**: Utilizado extensivamente como broker de mensajes para colas de `DomainAction` y como almacén temporal para el estado y metadatos de las tareas.

## 5. Capacidades Actuales

- Recepción de documentos vía subida de archivos, URL o texto plano.
- Validación de archivos (tipo, tamaño).
- Extracción de texto de múltiples formatos (PDF, DOCX, HTML, TXT, imágenes básicas, etc.) usando LlamaIndex.
- Fragmentación (chunking) inteligente de texto con LlamaIndex, configurable.
- Comunicación pseudo asíncrona con el Embedding Service para solicitar embeddings.
- Notificaciones en tiempo real del progreso y estado de las tareas a través de WebSockets.
- API REST para iniciar ingestiones, consultar estado de tareas y solicitar cancelación.
- Sistema de workers en pool para procesamiento paralelo.

