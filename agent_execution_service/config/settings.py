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
    
    # Cache de configuraciones
    agent_config_cache_ttl: int = Field(
        600,  # Aumentado a 10 minutos (estándar)
        description="TTL del cache de configuraciones de agente (segundos)"
    )
    
    # Cache de conversaciones
    conversation_cache_ttl: int = Field(
        1200,  # 20 minutos por defecto
        description="TTL del cache de historiales de conversación (segundos)"
    )
    
    # Límite de mensajes en caché por defecto
    default_conversation_cache_limit: int = Field(
        20,  # 20 mensajes por defecto
        description="Número máximo de mensajes para mantener en caché local de conversación"
    )
    
    # Límites por tier
    tier_limits: dict = Field(
        default={
            "free": {
                "max_iterations": 3, 
                "max_tools": 2, 
                "timeout": 30,
                "conversation_cache_ttl": 600,    # 10 minutos
                "conversation_cache_limit": 10,   # Máximo 10 mensajes en caché
                "wait_for_persistence": True,     # Esperar confirmación en tier gratuito
            },
            "advance": {
                "max_iterations": 5, 
                "max_tools": 5, 
                "timeout": 60,
                "conversation_cache_ttl": 900,    # 15 minutos
                "conversation_cache_limit": 20,   # Máximo 20 mensajes en caché
                "wait_for_persistence": False,    # No esperar confirmación
            },
            "professional": {
                "max_iterations": 10, 
                "max_tools": 10, 
                "timeout": 120,
                "conversation_cache_ttl": 1200,   # 20 minutos
                "conversation_cache_limit": 40,   # Máximo 40 mensajes en caché
                "wait_for_persistence": False,    # No esperar confirmación
            },
            "enterprise": {
                "max_iterations": 20, 
                "max_tools": None, 
                "timeout": 300,
                "conversation_cache_ttl": 1800,   # 30 minutos
                "conversation_cache_limit": 100,  # Máximo 100 mensajes en caché
                "wait_for_persistence": False,    # No esperar confirmación
            }
        },
        description="Límites y configuraciones por tier"
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