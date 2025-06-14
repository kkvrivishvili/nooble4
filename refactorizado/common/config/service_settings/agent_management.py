"""
Definición de la configuración específica para Agent Management Service.
"""
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..settings import CommonAppSettings # Ajustado para la nueva ubicación

class AgentManagementSettings(CommonAppSettings):
    """Configuración específica para Agent Management Service."""

    model_config = SettingsConfigDict(
        env_prefix='AMS_',
        extra='ignore',
        env_file='.env'
    )

    # Campos que estaban en la antigua BaseSettings y no están en CommonAppSettings,
    # o que son específicos de AgentManagementSettings.
    # service_name, environment, log_level, redis_url son heredados de CommonAppSettings.

    service_version: str = Field("1.0.0", description="Versión del servicio")
    http_timeout_seconds: int = Field(30, description="Timeout HTTP para llamadas salientes")

    # database_url es heredado de CommonAppSettings, pero aquí especificamos un default particular para AMS.
    # Pydantic tomará este default si AMS_DATABASE_URL no está en el entorno.
    database_url: str = Field(
        "postgresql://user:pass@localhost/nooble_agents", 
        description="URL de base de datos para agentes. Hereda de CommonAppSettings pero con default específico para AMS."
    )

    # Campos específicos del Agent Management Service
    domain_name: str = Field("management", description="Dominio específico para colas y lógica del servicio de gestión de agentes.")

    # URLs de servicios externos para validación
    ingestion_service_url: str = Field(
        "http://localhost:8006",
        description="URL del Ingestion Service para validar collections"
    )
    execution_service_url: str = Field(
        "http://localhost:8005", 
        description="URL del Agent Execution Service para invalidación de caché"
    )
    
    # Cache de configuraciones
    agent_config_cache_ttl: int = Field(
        300,
        description="TTL del cache de configuraciones de agente (segundos)"
    )
    
    # Configuración de templates
    templates_path: str = Field(
        "agent_management_service/templates", # Esta ruta es relativa al directorio raíz del servicio AMS
        description="Ruta base para templates del sistema"
    )
    
    # Validación
    enable_collection_validation: bool = Field(
        True,
        description="Habilitar validación de collections con Ingestion Service"
    )

    # Nuevos campos configurables movidos desde constants.py
    worker_sleep_seconds: float = Field(
        1.0, 
        description="Tiempo de espera para workers de AMS (segundos)"
    )
    collection_validation_cache_ttl: int = Field(
        300, 
        description="TTL para cache de validación de colecciones (segundos)"
    )
    template_cache_ttl: int = Field(
        3600, 
        description="TTL para cache de templates (segundos)"
    )
    public_url_cache_ttl: int = Field(
        3600, 
        description="TTL para cache de URLs públicas de agentes (segundos)"
    )
    slug_min_length: int = Field(
        5, 
        description="Longitud mínima para slugs de agentes públicos"
    )
    slug_max_length: int = Field(
        50, 
        description="Longitud máxima para slugs de agentes públicos"
    )
    default_agent_llm_model: str = Field(
        "gpt-4", 
        description="Modelo LLM por defecto para nuevos agentes"
    )
    default_agent_similarity_threshold: float = Field(
        0.75, 
        description="Umbral de similitud por defecto para agentes RAG"
    )
    default_agent_rag_results_limit: int = Field(
        5, 
        description="Límite de resultados RAG por defecto para agentes"
    )
