"""
Configuración del Agent Orchestrator Service.
MODIFICADO: Integración con sistema de colas por tier.
"""

from typing import List
from pydantic import Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class OrchestratorSettings(BaseSettings):
    """Configuración específica para Agent Orchestrator Service."""
    
    # NUEVO: Domain específico para colas
    domain_name: str = "orchestrator"
    
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
    
    # NUEVO: Configuración de colas
    callback_queue_prefix: str = Field(
        "orchestrator",
        description="Prefijo para colas de callback"
    )
    
    # NUEVO: Rate limiting específico del orchestrator
    max_requests_per_session: int = Field(
        100,
        description="Máximo requests por sesión por hora"
    )
    
    # Worker configuración
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    # NUEVO: Configuración de validación
    enable_access_validation: bool = Field(
        True,
        description="Habilitar validación de acceso tenant->agent"
    )
    validation_cache_ttl: int = Field(
        300,
        description="TTL del cache de validaciones (segundos)"
    )
    
    # NUEVO: Headers requeridos
    required_headers: List[str] = Field(
        default=["X-Tenant-ID", "X-Agent-ID", "X-Tenant-Tier", "X-Session-ID"],
        description="Headers requeridos para requests"
    )
    
    # NUEVO: Performance tracking
    enable_performance_tracking: bool = Field(
        True,
        description="Habilitar tracking de performance"
    )
    
    class Config:
        env_prefix = "ORCHESTRATOR_"

def get_settings() -> OrchestratorSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-orchestrator-service")
    return OrchestratorSettings(**base_settings.model_dump())