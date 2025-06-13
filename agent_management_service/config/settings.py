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

