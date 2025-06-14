"""
Constantes para el Agent Management Service.

Este módulo define constantes y valores estáticos utilizados por el servicio
de gestión de agentes. Los valores configurables se gestionan a través de
la clase AgentManagementSettings.
"""

# Constantes de Colas y Processing
# (Las configuraciones de colas ahora se gestionan en AgentManagementSettings)

# Constantes para Templates de Agentes
class AgentTemplateTypes:
    RAG = "rag"
    CONVERSATIONAL = "conversational"
    SEARCH = "search"
    WORKFLOW = "workflow"
    CUSTOM = "custom"

# Templates predefinidos disponibles en el código.
# Si estos necesitan ser configurables dinámicamente, deberían gestionarse
# a través de la base de datos o un sistema de configuración más avanzado.
DEFAULT_TEMPLATES = [
    "customer-support",
    "knowledge-base",
    "data-analyst", 
    "programming-assistant",
    "creative-writer"
]

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
