"""
Constantes para el Embedding Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de generación de embeddings.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "embedding-service"
DEFAULT_DOMAIN = "embedding"
VERSION = "1.0.0"

# Constantes de Proveedores de Embeddings
class EmbeddingProviders:
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    SENTENCE_TRANSFORMERS = "sentence_transformers"

# Modelos por defecto para cada proveedor
DEFAULT_MODELS = {
    EmbeddingProviders.OPENAI: "text-embedding-3-large",
    EmbeddingProviders.AZURE_OPENAI: "text-embedding-ada-002",
    EmbeddingProviders.COHERE: "embed-english-v3.0",
    EmbeddingProviders.HUGGINGFACE: "sentence-transformers/all-mpnet-base-v2",
    EmbeddingProviders.SENTENCE_TRANSFORMERS: "all-mpnet-base-v2"
}

# Dimensiones por defecto para cada modelo
DEFAULT_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    "embed-english-v3.0": 1024,
    "all-mpnet-base-v2": 768
}

# Constantes para formatos de codificación
class EncodingFormats:
    FLOAT = "float"
    BASE64 = "base64"
    BINARY = "binary"

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "embedding"
DEFAULT_WORKER_SLEEP_SECONDS = 0.1

# Nombres de colas
class QueueNames:
    EMBEDDING_GENERATE = "embedding:generate"
    EMBEDDING_CALLBACK = "embedding:callback"
    EMBEDDING_VALIDATE = "embedding:validate"

# Constantes para procesamiento por lotes
DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_TEXT_LENGTH = 8192
DEFAULT_TRUNCATION_STRATEGY = "end"

# Constantes para Cache
DEFAULT_CACHE_TTL_SECONDS = 86400  # 24 horas
DEFAULT_CACHE_MAX_SIZE = 10000  # Número máximo de entradas en caché

# Constantes para Rate Limiting por Tier
MAX_EMBEDDINGS_PER_HOUR_BY_TIER = {
    "free": 100,
    "advance": 1000,
    "professional": 10000,
    "enterprise": 100000
}

MAX_BATCH_SIZE_BY_TIER = {
    "free": 10,
    "advance": 50,
    "professional": 100,
    "enterprise": 500
}

MAX_TEXT_LENGTH_BY_TIER = {
    "free": 4096,
    "advance": 8192,
    "professional": 16384,
    "enterprise": 32768
}

# Constantes para timeout y reintentos
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUSES = [408, 500, 502, 503, 504]

# Constantes para métricas de rendimiento
SLOW_EMBED_THRESHOLD_MS = 500

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    EMBED = "/embed"
    BATCH_EMBED = "/batch-embed"
    ASYNC_EMBED = "/async-embed"
    MODELS = "/models"
    DIMENSIONS = "/dimensions"
    STATUS = "/status/{job_id}"
    METRICS = "/metrics"
