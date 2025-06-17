"""
Constantes para el Query Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de consultas mediante RAG. Los valores configurables se gestionan a través de
QueryServiceSettings en la configuración centralizada.
"""

# Constantes de Proveedores de LLM (usado para identificar proveedores soportados)
class LLMProviders:
    GROQ = "groq"
    # Añadir otros proveedores según sea necesario

# Nombres de colas
# (Los nombres de las colas ahora se construyen dinámicamente en el código
# utilizando los valores de 'domain_name' y 'process_query_queue_segment' de QueryServiceSettings,
# junto con la lógica de QueueManager para los sufijos estándar como ':actions' o ':callback'.)

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
