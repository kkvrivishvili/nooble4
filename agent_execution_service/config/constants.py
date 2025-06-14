"""
Constantes para el Agent Execution Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de ejecución de agentes. Las configuraciones variables se gestionan en settings.py.
"""

# Constantes de LangChain
DEFAULT_CONVERSATION_MEMORY_KEY = None

# Constantes de Colas y Processing
# (Si hay constantes específicas de colas que no son configurables, van aquí)

# Constantes para LLM
class LLMProviders:
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    COHERE = "cohere"

# Modelos por defecto para cada proveedor (usado por el validador en settings.py)
DEFAULT_MODELS = {
    LLMProviders.OPENAI: "gpt-4",
    LLMProviders.ANTHROPIC: "claude-3-sonnet-20240229",
    LLMProviders.GROQ: "llama3-70b-8192",
    LLMProviders.AZURE_OPENAI: "gpt-4", # Asegúrate que este sea el nombre correcto del deployment/modelo en Azure
    LLMProviders.OLLAMA: "llama3",
    LLMProviders.COHERE: "command-r-plus"
}

# Temperaturas por defecto para cada tier
# Si estos valores necesitan ser configurables por entorno, deben moverse a settings.py
DEFAULT_TEMPERATURES = {
    "free": 0.7,
    "advance": 0.5,
    "professional": 0.3,
    "enterprise": 0.2
}

# Constantes para Tool Processing (si son fijas y no configurables por entorno)
MAX_FUNCTION_CALLS = 25
TOOL_TIMEOUT_SECONDS = 30

# Constantes para loaders y parsers (si son fijas)
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Constantes para streaming de respuestas (si son fijas)
STREAM_CHUNK_SIZE = 10  # tokens

# Constantes para cache
# (Si hay constantes específicas de cache que no son configurables, van aquí)

# Constantes para uso de bases de conocimiento y RAG (si son fijas)
MAX_KNOWLEDGE_BASE_RESULTS = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.75

# Constantes para validación por tier
# (Si hay constantes específicas de validación que no son configurables, van aquí)

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    EXECUTE = "/execute"
    STREAM = "/stream"
    TOOLS = "/tools"
    STOP = "/stop/{execution_id}"
