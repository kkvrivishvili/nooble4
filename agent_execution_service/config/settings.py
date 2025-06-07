"""
Configuración del Agent Execution Service.
MODIFICADO: Integración con sistema de colas por tier.
"""

from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class ExecutionSettings(BaseSettings):
    """Configuración específica para Agent Execution Service."""
    
    # NUEVO: Domain específico para colas
    domain_name: str = "execution"
    
    # URLs de servicios externos
    embedding_service_url: str = Field(
        "http://localhost:8001",
        description="URL del Embedding Service"
    )
    query_service_url: str = Field(
        "http://localhost:8002", 
        description="URL del Query Service"
    )
    conversation_service_url: str = Field(
        "http://localhost:8004",
        description="URL del Conversation Service"
    )
    agent_management_service_url: str = Field(
        "http://localhost:8003",
        description="URL del Agent Management Service"
    )
    
    # LangChain configuración
    default_agent_type: str = Field(
        "conversational",
        description="Tipo de agente por defecto"
    )
    max_iterations: int = Field(
        5,
        description="Máximo de iteraciones para agentes"
    )
    max_execution_time: int = Field(
        120,
        description="Tiempo máximo de ejecución (segundos)"
    )
    
    # NUEVO: Configuración de colas
    callback_queue_prefix: str = Field(
        "orchestrator",
        description="Prefijo para colas de callback hacia orchestrator"
    )
    
    # NUEVO: Cache de configuraciones
    agent_config_cache_ttl: int = Field(
        300,
        description="TTL del cache de configuraciones de agente (segundos)"
    )
    
    # NUEVO: Límites por tier
    tier_limits: dict = Field(
        default={
            "free": {"max_iterations": 3, "max_tools": 2, "timeout": 30},
            "advance": {"max_iterations": 5, "max_tools": 5, "timeout": 60},
            "professional": {"max_iterations": 10, "max_tools": 10, "timeout": 120},
            "enterprise": {"max_iterations": 20, "max_tools": None, "timeout": 300}
        },
        description="Límites por tier"
    )
    
    # Worker configuración
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    # NUEVO: Performance tracking
    enable_execution_tracking: bool = Field(
        True,
        description="Habilitar tracking de métricas de ejecución"
    )
    
    class Config:
        env_prefix = "EXECUTION_"

def get_settings() -> ExecutionSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-execution-service")
    return ExecutionSettings(**base_settings.model_dump())