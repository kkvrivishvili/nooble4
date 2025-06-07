"""
Configuración específica para Agent Management Service.
INTEGRADO: Con sistema de configuración base común.
"""

from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class AgentManagementSettings(BaseSettings):
    """Configuración específica para Agent Management Service."""
    
    # NUEVO: Domain específico para colas
    domain_name: str = "management"
    
    # URLs de servicios externos para validación
    ingestion_service_url: str = Field(
        "http://localhost:8006",
        description="URL del Ingestion Service para validar collections"
    )
    execution_service_url: str = Field(
        "http://localhost:8005", 
        description="URL del Agent Execution Service para cache invalidation"
    )
    
    # Base de datos (futuro)
    database_url: str = Field(
        "postgresql://user:pass@localhost/nooble_agents",
        description="URL de base de datos para agentes"
    )
    
    # Cache de configuraciones
    agent_config_cache_ttl: int = Field(
        300,
        description="TTL del cache de configuraciones de agente (segundos)"
    )
    
    # Límites por tier
    tier_limits: dict = Field(
        default={
            "free": {
                "max_agents": 1,
                "available_tools": ["basic_chat", "datetime"],
                "available_models": ["llama3-8b-8192"],
                "max_collections_per_agent": 1,
                "templates_access": ["customer_service"]
            },
            "advance": {
                "max_agents": 3,
                "available_tools": ["basic_chat", "datetime", "rag_query", "calculator"],
                "available_models": ["llama3-8b-8192", "llama3-70b-8192"],
                "max_collections_per_agent": 3,
                "templates_access": ["customer_service", "knowledge_base"]
            },
            "professional": {
                "max_agents": 10,
                "available_tools": ["all"],
                "available_models": ["all"],
                "max_collections_per_agent": 10,
                "templates_access": ["all"],
                "custom_templates": True
            },
            "enterprise": {
                "max_agents": None,
                "available_tools": ["all"],
                "available_models": ["all"],
                "max_collections_per_agent": None,
                "templates_access": ["all"],
                "custom_templates": True,
                "advanced_workflows": True
            }
        },
        description="Límites y capacidades por tier"
    )
    
    # Configuración de templates
    templates_path: str = Field(
        "agent_management_service/templates",
        description="Ruta base para templates del sistema"
    )
    
    # Validación
    enable_collection_validation: bool = Field(
        True,
        description="Habilitar validación de collections con Ingestion Service"
    )
    
    class Config:
        env_prefix = "AGENT_MANAGEMENT_"

def get_settings() -> AgentManagementSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-management-service")
    return AgentManagementSettings(**base_settings.model_dump())

