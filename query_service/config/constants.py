"""
Constantes para el Query Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de consultas mediante RAG.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "query-service"
DEFAULT_DOMAIN = "query"
VERSION = "1.0.0"

# Constantes de LLM
class LLMProviders:
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"

# Modelos por defecto para cada proveedor
DEFAULT_MODELS = {
    LLMProviders.GROQ: "llama3-70b-8192",
    LLMProviders.OPENAI: "gpt-4",
    LLMProviders.ANTHROPIC: "claude-3-sonnet-20240229",
    LLMProviders.AZURE_OPENAI: "gpt-4",
    LLMProviders.OLLAMA: "llama3"
}

# Parámetros por defecto para LLMs
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TOP_P = 0.95
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "query"
DEFAULT_WORKER_SLEEP_SECONDS = 0.1

# Nombres de colas
class QueueNames:
    QUERY_SEARCH = "query:search"
    QUERY_GENERATE = "query:generate"
    QUERY_CALLBACK = "query:callback"

# Constantes para Cache
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hora
DEFAULT_VECTOR_CACHE_TTL_SECONDS = 600  # 10 minutos
DEFAULT_SIMILARITY_CACHE_TTL_SECONDS = 300  # 5 minutos

# Constantes para RAG
DEFAULT_MAX_RESULTS = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_MAX_VECTOR_SEARCH_TIME_SECONDS = 10
DEFAULT_CONTEXT_WINDOW_SIZE = 4000
DEFAULT_QUERY_EXPANSION_ENABLED = True

# Constantes para Rate Limiting por Tier
MAX_QUERIES_PER_HOUR_BY_TIER = {
    "free": 10,
    "advance": 50,
    "professional": 300,
    "enterprise": 1000
}

MAX_TOKENS_PER_QUERY_BY_TIER = {
    "free": 2000,
    "advance": 4000,
    "professional": 8000,
    "enterprise": 16000
}

MAX_RESULTS_BY_TIER = {
    "free": 3,
    "advance": 5,
    "professional": 10,
    "enterprise": 20
}

# Constantes para timeout y reintentos
DEFAULT_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUSES = [408, 500, 502, 503, 504]

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    QUERY = "/query"
    SEARCH = "/search"
    SIMILAR = "/similar"
    STATUS = "/status/{query_id}"
    METRICS = "/metrics"
