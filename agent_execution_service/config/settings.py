"""
Configuración del Agent Execution Service.
"""

from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class ExecutionSettings(BaseSettings):
    """Configuración específica para Agent Execution Service."""
    
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
    
    # Worker configuración
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    class Config:
        env_prefix = "EXECUTION_"

def get_settings() -> ExecutionSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-execution-service")
    return ExecutionSettings(**base_settings.model_dump())
