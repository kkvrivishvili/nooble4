"""
Constantes para el Agent Execution Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de ejecución de agentes.
"""

# Constantes Generales del Servicio
SERVICE_NAME = "agent-execution-service"
DEFAULT_DOMAIN = "agent-execution"
VERSION = "1.0.0"

# Constantes de LangChain
DEFAULT_CONVERSATION_MEMORY_KEY = "chat_history"
DEFAULT_LANGCHAIN_TIMEOUT = 600  # 10 minutos
DEFAULT_LANGCHAIN_VERBOSE = False
DEFAULT_MAX_ITERATIONS = 15
DEFAULT_MAX_EXECUTION_TIME = 300  # 5 minutos

# Constantes de Colas y Processing
CALLBACK_QUEUE_PREFIX = "agent-execution"
DEFAULT_WORKER_SLEEP_SECONDS = 1.0

# Constantes para LLM
class LLMProviders:
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    COHERE = "cohere"

# Modelos por defecto para cada proveedor
DEFAULT_MODELS = {
    LLMProviders.OPENAI: "gpt-4",
    LLMProviders.ANTHROPIC: "claude-3-sonnet-20240229",
    LLMProviders.GROQ: "llama3-70b-8192",
    LLMProviders.AZURE_OPENAI: "gpt-4",
    LLMProviders.OLLAMA: "llama3",
    LLMProviders.COHERE: "command-r-plus"
}

# Temperaturas por defecto para cada tier
DEFAULT_TEMPERATURES = {
    "free": 0.7,
    "advance": 0.5,
    "professional": 0.3,
    "enterprise": 0.2
}

# Constantes para Tool Processing
MAX_TOOLS_PER_AGENT = 10
MAX_FUNCTION_CALLS = 25
TOOL_TIMEOUT_SECONDS = 30

# Constantes para loaders y parsers
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Constantes para streaming de respuestas
STREAM_CHUNK_SIZE = 10  # tokens

# Constantes para cache
MEMORY_CACHE_TTL_SECONDS = 3600  # 1 hora
EXECUTION_CACHE_TTL_SECONDS = 600  # 10 minutos

# Constantes para uso de bases de conocimiento y RAG
MAX_KNOWLEDGE_BASE_RESULTS = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75

# Constantes para validación por tier
MAX_TOOLS_BY_TIER = {
    "free": 3,
    "advance": 5,
    "professional": 8,
    "enterprise": 15
}

MAX_TOKENS_BY_TIER = {
    "free": 4000,
    "advance": 8000, 
    "professional": 16000,
    "enterprise": 32000
}

MAX_MESSAGES_BY_TIER = {
    "free": 10,
    "advance": 25,
    "professional": 50,
    "enterprise": 100
}

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    EXECUTE = "/execute"
    STREAM = "/stream"
    TOOLS = "/tools"
    STOP = "/stop/{execution_id}"
