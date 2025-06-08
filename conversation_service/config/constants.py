"""
Constantes para el Conversation Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de gestión de conversaciones.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "conversation-service"
DEFAULT_DOMAIN = "conversation"
VERSION = "1.0.0"

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "conversation"
DEFAULT_WORKER_SLEEP_SECONDS = 0.1

# Nombres de colas
class QueueNames:
    CONVERSATION_SAVE = "conversation:save"
    CONVERSATION_RETRIEVE = "conversation:retrieve"
    CONVERSATION_ANALYZE = "conversation:analyze"
    CONVERSATION_CALLBACK = "conversation:callback"

# Constantes para Cache
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hora
CONVERSATION_CACHE_TTL_SECONDS = 600  # 10 minutos
SESSION_CACHE_TTL_SECONDS = 1800  # 30 minutos

# Constantes para Analytics
ANALYTICS_ENABLED = True
DEFAULT_ANALYTICS_SAMPLE_RATE = 0.1  # 10% de conversaciones
MAX_ANALYTICS_EVENTS_BATCH_SIZE = 100

# Constantes para CRM
CRM_INTEGRATION_ENABLED = False
CRM_SYNC_INTERVAL_SECONDS = 300  # 5 minutos

# Constantes para Retención por Tier
CONVERSATION_RETENTION_DAYS_BY_TIER = {
    "free": 7,
    "advance": 30,
    "professional": 90,
    "enterprise": 365
}

MAX_CONVERSATIONS_BY_TIER = {
    "free": 10,
    "advance": 100,
    "professional": 1000,
    "enterprise": 10000
}

MAX_MESSAGES_PER_CONVERSATION_BY_TIER = {
    "free": 20,
    "advance": 50,
    "professional": 100,
    "enterprise": 500
}

# Constantes para Sentiment Analysis
SENTIMENT_ANALYSIS_ENABLED = False
SENTIMENT_ANALYSIS_CONFIDENCE_THRESHOLD = 0.7

# Constantes para Exported Formats
class ExportFormats:
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"

# Constantes para Búsqueda y Filtrado
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_CONVERSATIONS_PAGE_SIZE = 20

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    CONVERSATIONS = "/conversations"
    CONVERSATION_DETAIL = "/conversations/{conversation_id}"
    MESSAGES = "/conversations/{conversation_id}/messages"
    MESSAGE_DETAIL = "/conversations/{conversation_id}/messages/{message_id}"
    EXPORT = "/conversations/{conversation_id}/export"
    ANALYTICS = "/analytics"
    SEARCH = "/search"

# Constantes para Tipos de Mensajes
class MessageTypes:
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    TOOL = "tool"
    ERROR = "error"
