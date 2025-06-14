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

# Constantes para cache
# (Si hay constantes específicas de cache que no son configurables, van aquí)

# Constantes para validación por tier
# (Si hay constantes específicas de validación que no son configurables, van aquí)

# Constantes para Endpoints
class EndpointPaths:
    HEALTH = "/health"
    EXECUTE = "/execute"
    STREAM = "/stream"
    TOOLS = "/tools"
    STOP = "/stop/{execution_id}"
