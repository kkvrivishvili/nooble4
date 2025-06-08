# Análisis del Ingestion Service

## 1. Variables de Entorno Necesarias

El Ingestion Service utiliza las siguientes variables de entorno, ahora estandarizadas con el prefijo `INGESTION_`:

### Variables Base (comunes a todos los servicios)
- `SERVICE_VERSION`: Versión del servicio. Valor por defecto: "1.0.0"
- `LOG_LEVEL`: Nivel de logging. Valor por defecto: "INFO"
- `REDIS_URL`: URL de conexión a Redis. Valor por defecto: "redis://localhost:6379"
- `DATABASE_URL`: URL de conexión a la base de datos (cuando aplica). Valor por defecto: ""
- `HTTP_TIMEOUT_SECONDS`: Timeout para peticiones HTTP. Valor por defecto: 30

### Variables Específicas del Ingestion Service (con prefijo INGESTION_)
- `INGESTION_DOMAIN_NAME`: Dominio para colas. Valor por defecto: "ingestion"
- `INGESTION_HOST`: Host del servidor. Valor por defecto: "0.0.0.0"
- `INGESTION_PORT`: Puerto del servidor. Valor por defecto: 8000
- `INGESTION_REDIS_HOST`: Host de Redis. Valor por defecto: "localhost"
- `INGESTION_REDIS_PORT`: Puerto de Redis. Valor por defecto: 6379
- `INGESTION_REDIS_PASSWORD`: Contraseña de Redis. Valor por defecto: None
- `INGESTION_REDIS_DB`: Base de datos Redis. Valor por defecto: 0
- `INGESTION_REDIS_QUEUE_PREFIX`: Prefijo para colas Redis. Valor por defecto: "ingestion"
- `INGESTION_DOCUMENT_QUEUE`: Cola de procesamiento de documentos. Valor por defecto: "document:processing"
- `INGESTION_CHUNKING_QUEUE`: Cola de fragmentación. Valor por defecto: "document:chunking"
- `INGESTION_EMBEDDING_CALLBACK_QUEUE`: Cola de callbacks de embeddings. Valor por defecto: "embedding:callback"
- `INGESTION_TASK_STATUS_QUEUE`: Cola de estado de tareas. Valor por defecto: "task:status"
- `INGESTION_WORKER_COUNT`: Número de workers. Valor por defecto: 2
- `INGESTION_MAX_CONCURRENT_TASKS`: Máximo de tareas concurrentes. Valor por defecto: 5
- `INGESTION_JOB_TIMEOUT`: Timeout de trabajos (segundos). Valor por defecto: 3600 (1 hora)
- `INGESTION_REDIS_LOCK_TIMEOUT`: Timeout de bloqueos Redis. Valor por defecto: 600 (10 minutos)
- `INGESTION_WORKER_SLEEP_TIME`: Tiempo entre polls (segundos). Valor por defecto: 0.1
- `INGESTION_MAX_FILE_SIZE`: Tamaño máximo de archivo (bytes). Valor por defecto: 10485760 (10MB)
- `INGESTION_MAX_DOCUMENT_SIZE`: Tamaño máximo de documento texto (bytes). Valor por defecto: 1048576 (1MB)
- `INGESTION_MAX_URL_SIZE`: Tamaño máximo de contenido URL (bytes). Valor por defecto: 10485760 (10MB)
- `INGESTION_MAX_CHUNKS_PER_DOCUMENT`: Máximo fragmentos por documento. Valor por defecto: 1000
- `INGESTION_DEFAULT_CHUNK_SIZE`: Tamaño predeterminado de fragmentos. Valor por defecto: 512
- `INGESTION_DEFAULT_CHUNK_OVERLAP`: Superposición entre fragmentos. Valor por defecto: 50
- `INGESTION_DEFAULT_CHUNKING_STRATEGY`: Estrategia de fragmentación. Valor por defecto: "sentence"
- `INGESTION_EMBEDDING_MODEL`: Modelo de embedding. Valor por defecto: "text-embedding-ada-002"
- `INGESTION_EMBEDDING_SERVICE_URL`: URL del servicio de embeddings. Valor por defecto: "http://embedding-service:8000"
- `INGESTION_EMBEDDING_SERVICE_TIMEOUT`: Timeout para servicio de embeddings. Valor por defecto: 60
- `INGESTION_STORAGE_TYPE`: Tipo de almacenamiento (local, s3, azure). Valor por defecto: "local"
- `INGESTION_LOCAL_STORAGE_PATH`: Ruta para almacenamiento local. Valor por defecto: "/tmp/ingestion"
- `INGESTION_API_KEY_HEADER`: Header para API Key. Valor por defecto: "X-API-Key"
- `INGESTION_ADMIN_API_KEY`: API Key para administrador. Valor por defecto: None
- `INGESTION_AUTO_START_WORKERS`: Iniciar workers automáticamente. Valor por defecto: True
- `INGESTION_CORS_ORIGINS`: Orígenes permitidos para CORS. Valor por defecto: ["*"]

## 2. Variables de Configuración para `constants.py` (implementado)

Se ha implementado el archivo `constants.py` en el Ingestion Service con las siguientes constantes:

### Constantes Generales del Servicio
- `SERVICE_NAME`: "ingestion-service"
- `DEFAULT_DOMAIN`: "ingestion"
- `VERSION`: "1.0.0"
- `DEFAULT_HOST`: "0.0.0.0"
- `DEFAULT_PORT`: 8000
- `DEFAULT_LOG_LEVEL`: "INFO"

### Constantes para Redis y Colas
- `DEFAULT_REDIS_HOST`: "localhost"
- `DEFAULT_REDIS_PORT`: 6379
- `DEFAULT_REDIS_DB`: 0
- `DEFAULT_REDIS_QUEUE_PREFIX`: "ingestion"

### Constantes para Nombres de Colas
```python
class QueueNames:
    DOCUMENT_PROCESSING = "document:processing"
    DOCUMENT_CHUNKING = "document:chunking"
    EMBEDDING_CALLBACK = "embedding:callback"
    TASK_STATUS = "task:status"
```

### Constantes para Workers y Procesamiento
- `DEFAULT_WORKER_COUNT`: 2
- `MAX_CONCURRENT_TASKS`: 5
- `DEFAULT_JOB_TIMEOUT`: 3600  # 1 hora
- `DEFAULT_REDIS_LOCK_TIMEOUT`: 600  # 10 minutos
- `DEFAULT_WORKER_SLEEP_TIME`: 0.1  # 100ms

### Constantes para Límites de Tamaño
- `DEFAULT_MAX_FILE_SIZE`: 10485760  # 10MB
- `DEFAULT_MAX_DOCUMENT_SIZE`: 1048576  # 1MB
- `DEFAULT_MAX_URL_SIZE`: 10485760  # 10MB
- `DEFAULT_MAX_CHUNKS_PER_DOCUMENT`: 1000

### Constantes para Chunking
- `DEFAULT_CHUNK_SIZE`: 512
- `DEFAULT_CHUNK_OVERLAP`: 50

### Constantes para Estrategias de Chunking
```python
class ChunkingStrategies:
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    TOKEN = "token"
    CHARACTER = "character"
```

### Constantes para Embedding
- `DEFAULT_EMBEDDING_MODEL`: "text-embedding-ada-002"
- `DEFAULT_EMBEDDING_SERVICE_URL`: "http://embedding-service:8000"
- `DEFAULT_EMBEDDING_SERVICE_TIMEOUT`: 60

### Constantes para Almacenamiento
```python
class StorageTypes:
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
```
- `DEFAULT_LOCAL_STORAGE_PATH`: "/tmp/ingestion"

### Constantes para Autenticación
- `DEFAULT_API_KEY_HEADER`: "X-API-Key"

### Constantes para Estados de Tareas
```python
class TaskStates:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Constantes para Tipos de Documentos
```python
class DocumentTypes:
    TEXT = "text"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    MD = "markdown"
    URL = "url"
```

### Constantes para Rate Limiting por Tier
```python
MAX_DOCUMENTS_PER_HOUR_BY_TIER = {
    "free": 5,
    "advance": 20,
    "professional": 100,
    "enterprise": 500
}

MAX_FILE_SIZE_BY_TIER = {
    "free": 5 * 1024 * 1024,  # 5MB
    "advance": 10 * 1024 * 1024,  # 10MB
    "professional": 50 * 1024 * 1024,  # 50MB
    "enterprise": 100 * 1024 * 1024  # 100MB
}

MAX_CHUNKS_PER_DOCUMENT_BY_TIER = {
    "free": 500,
    "advance": 1000,
    "professional": 5000,
    "enterprise": 10000
}
```

### Constantes para Endpoints
```python
class EndpointPaths:
    HEALTH = "/health"
    DOCUMENTS = "/documents"
    DOCUMENT_DETAIL = "/documents/{document_id}"
    CHUNKS = "/documents/{document_id}/chunks"
    TASKS = "/tasks"
    TASK_DETAIL = "/tasks/{task_id}"
    WEBSOCKET = "/ws/{task_id}"
    UPLOADS = "/upload"
```

### Nota sobre Estandarización de Variables de Entorno

Se ha completado la estandarización de las variables de entorno del servicio para usar el prefijo `INGESTION_`, siguiendo el patrón de los demás servicios en el proyecto nooble4. Estos cambios incluyen:

1. Actualizar la clase de configuración a `IngestionServiceSettings` con `env_prefix = "INGESTION_"`.
2. Renombrar las propiedades de la clase para usar snake_case.
3. Agregar descripciones detalladas a cada campo para mejor documentación.

Esto garantiza la coherencia con los demás servicios y facilita la configuración y mantenimiento del proyecto.
