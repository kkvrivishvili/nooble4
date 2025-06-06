"""
Configuración del Agent Orchestrator Service.
"""

from typing import List
from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class OrchestratorSettings(BaseSettings):
    """Configuración específica para Agent Orchestrator Service."""
    
    # WebSocket configuración
    websocket_ping_interval: int = Field(
        30,
        description="Intervalo de ping para WebSocket (segundos)"
    )
    websocket_ping_timeout: int = Field(
        10,
        description="Timeout para pong de WebSocket (segundos)"
    )
    max_websocket_connections: int = Field(
        1000,
        description="Máximo de conexiones WebSocket simultáneas"
    )
    
    # Worker configuración
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    class Config:
        env_prefix = "ORCHESTRATOR_"

def get_settings() -> OrchestratorSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-orchestrator-service")
    return OrchestratorSettings(**base_settings.model_dump())
