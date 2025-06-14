"""
Constantes para el Query Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de consultas mediante RAG. Los valores configurables se gestionan a través de
QueryServiceSettings en la configuración centralizada.
"""

# Versión del servicio (puede ser útil para logs o health checks)
VERSION = "1.0.0"

# Constantes de Proveedores de LLM (usado para identificar proveedores soportados)
class LLMProviders:
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    # Añadir otros proveedores según sea necesario

# Nombres de colas específicas del Query Service (el prefijo global y de servicio viene de settings)
# Estos son los nombres *base* de las colas que el servicio escucha o publica.
# La nomenclatura completa de la cola se construye usando QueueManager (ver MEMORY[9395f05a-ecfb-4003-ad50-a3deff0156af])
class QueueNames:
    # Cola principal donde el Query Service recibe acciones de consulta
    PROCESS_QUERY_ACTION = "process_query" # Ejemplo: nooble4:dev:query:process_query:actions
    
    # Podrían existir otras colas para tareas internas o callbacks específicos del QS
    # Por ejemplo, si el QS necesita realizar sub-tareas asíncronas internamente.
    # QUERY_SUBTASK_EXAMPLE = "internal_subtask"

# Constantes para Endpoints del API del Query Service
class EndpointPaths:
    HEALTH = "/health" # Endpoint de health check
    QUERY_SUBMIT = "/query" # Endpoint para enviar una nueva consulta (asíncrona)
    QUERY_SYNC = "/query/sync" # Endpoint para enviar una consulta y esperar respuesta (síncrona)
    QUERY_STATUS = "/query/status/{query_id}" # Endpoint para obtener el estado de una consulta
    SEARCH_DIRECT = "/search/direct" # Endpoint para realizar una búsqueda vectorial directa (sin LLM)
    # METRICS = "/metrics" # Endpoint para métricas (si se exponen vía HTTP)

# Otras constantes no configurables específicas del Query Service:
# Por ejemplo, tipos de acciones de dominio que maneja o emite, si son fijas.
# ACTION_TYPE_PROCESS_QUERY = "query.process"
# ACTION_TYPE_QUERY_RESULT_CALLBACK = "query.result.callback"
