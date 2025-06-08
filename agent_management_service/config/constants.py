"""
Constantes para el Agent Management Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de gestión de agentes.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "agent-management-service"
DEFAULT_DOMAIN = "agent-management"
VERSION = "1.0.0"

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "agent-management"
DEFAULT_WORKER_SLEEP_SECONDS = 1.0

# Constantes para Templates de Agentes
class AgentTemplateTypes:
    RAG = "rag"
    CONVERSATIONAL = "conversational"
    SEARCH = "search"
    WORKFLOW = "workflow"
    CUSTOM = "custom"

# Templates predefinidos disponibles
DEFAULT_TEMPLATES = [
    "customer-support",
    "knowledge-base",
    "data-analyst", 
    "programming-assistant",
    "creative-writer"
]

# Constantes para Validación por Tier
MAX_AGENTS_BY_TIER = {
    "free": 2,
    "advance": 5,
    "professional": 20,
    "enterprise": 100
}

MAX_COLLECTIONS_PER_AGENT_BY_TIER = {
    "free": 1,
    "advance": 3,
    "professional": 10,
    "enterprise": 50
}

MAX_TOOLS_PER_AGENT_BY_TIER = {
    "free": 2,
    "advance": 5,
    "professional": 10,
    "enterprise": 25
}

ALLOWED_TEMPLATE_TYPES_BY_TIER = {
    "free": [AgentTemplateTypes.RAG, AgentTemplateTypes.CONVERSATIONAL],
    "advance": [AgentTemplateTypes.RAG, AgentTemplateTypes.CONVERSATIONAL, AgentTemplateTypes.SEARCH],
    "professional": [AgentTemplateTypes.RAG, AgentTemplateTypes.CONVERSATIONAL, AgentTemplateTypes.SEARCH, AgentTemplateTypes.WORKFLOW],
    "enterprise": [AgentTemplateTypes.RAG, AgentTemplateTypes.CONVERSATIONAL, AgentTemplateTypes.SEARCH, AgentTemplateTypes.WORKFLOW, AgentTemplateTypes.CUSTOM]
}

CUSTOM_PROMPTS_ALLOWED_BY_TIER = {
    "free": False,
    "advance": True,
    "professional": True,
    "enterprise": True
}

# Constantes para Cache
AGENT_CACHE_TTL_SECONDS = 600  # 10 minutos
COLLECTION_VALIDATION_CACHE_TTL_SECONDS = 300  # 5 minutos
TEMPLATE_CACHE_TTL_SECONDS = 3600  # 1 hora

# Constantes para URLs Públicas
PUBLIC_URL_CACHE_TTL_SECONDS = 3600  # 1 hora
SLUG_MIN_LENGTH = 5
SLUG_MAX_LENGTH = 50

# Constantes para Analytics
ANALYTICS_RETENTION_DAYS = {
    "free": 7,
    "advance": 30,
    "professional": 90,
    "enterprise": 365
}

# Constantes para LLM y conector a Query Service
DEFAULT_LLM_MODEL = "gpt-4"
DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_RAG_RESULTS_LIMIT = 5

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    AGENTS = "/agents"
    AGENT_DETAIL = "/agents/{agent_id}"
    TEMPLATES = "/templates"
    TEMPLATE_DETAIL = "/templates/{template_id}"
    PUBLIC_AGENT = "/public/{slug}"
    COLLECTIONS = "/agents/{agent_id}/collections"
    TOOLS = "/agents/{agent_id}/tools"
    ANALYTICS = "/agents/{agent_id}/analytics"
