"""
Constantes para el Ingestion Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de procesamiento y fragmentación de documentos.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "ingestion-service"
DEFAULT_DOMAIN = "ingestion"
VERSION = "1.0.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_LOG_LEVEL = "INFO"

# Constantes para Redis y Colas
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0
DEFAULT_REDIS_QUEUE_PREFIX = "ingestion"

# Constantes para Nombres de Colas
class QueueNames:
    DOCUMENT_PROCESSING = "document:processing"
    DOCUMENT_CHUNKING = "document:chunking"
    EMBEDDING_CALLBACK = "embedding:callback"
    TASK_STATUS = "task:status"

# Constantes para Workers y Procesamiento
DEFAULT_WORKER_COUNT = 2
MAX_CONCURRENT_TASKS = 5
DEFAULT_JOB_TIMEOUT = 3600  # 1 hora
DEFAULT_REDIS_LOCK_TIMEOUT = 600  # 10 minutos
DEFAULT_WORKER_SLEEP_TIME = 0.1  # 100ms

# Constantes para Límites de Tamaño
DEFAULT_MAX_FILE_SIZE = 10485760  # 10MB
DEFAULT_MAX_DOCUMENT_SIZE = 1048576  # 1MB
DEFAULT_MAX_URL_SIZE = 10485760  # 10MB
DEFAULT_MAX_CHUNKS_PER_DOCUMENT = 1000

# Constantes para Chunking
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50

# Constantes para Estrategias de Chunking
class ChunkingStrategies:
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    TOKEN = "token"
    CHARACTER = "character"

# Constantes para Embedding
DEFAULT_EMBEDDING_MODEL = "text-embedding-ada-002"
DEFAULT_EMBEDDING_SERVICE_URL = "http://embedding-service:8000"
DEFAULT_EMBEDDING_SERVICE_TIMEOUT = 60

# Constantes para Almacenamiento
class StorageTypes:
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"

DEFAULT_LOCAL_STORAGE_PATH = "/tmp/ingestion"

# Constantes para Autenticación
DEFAULT_API_KEY_HEADER = "X-API-Key"

# Constantes para Estados de Tareas
class TaskStates:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Constantes para Tipos de Documentos
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

# Constantes para Rate Limiting por Tier
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

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    DOCUMENTS = "/documents"
    DOCUMENT_DETAIL = "/documents/{document_id}"
    CHUNKS = "/documents/{document_id}/chunks"
    TASKS = "/tasks"
    TASK_DETAIL = "/tasks/{task_id}"
    WEBSOCKET = "/ws/{task_id}"
    UPLOADS = "/upload"
