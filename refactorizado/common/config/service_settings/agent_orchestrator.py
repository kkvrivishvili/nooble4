"""
Definición de la configuración específica para Agent Orchestrator Service.
"""
from typing import List

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings # Ajustado para la nueva ubicación

class OrchestratorSettings(CommonAppSettings):
    """Configuración específica para Agent Orchestrator Service."""

    model_config = SettingsConfigDict(
        env_prefix='AOS_',
        extra='ignore',
        env_file='.env'
    )

# Campos específicos de OrchestratorSettings o que anulan valores de CommonAppSettings.
# service_name, environment, log_level, redis_url, database_url, http_timeout_seconds son heredados de CommonAppSettings.

    service_version: str = Field("1.0.0", description="Versión del servicio")

    # Campos específicos del Orchestrator Service
    domain_name: str = Field("orchestrator", description="Dominio específico para colas y lógica del orquestador.")

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

    callback_queue_prefix: str = Field(
        "orchestrator",
        description="Prefijo para colas de callback"
    )

    max_requests_per_session: int = Field(
        100,
        description="Máximo requests por sesión por hora para rate limiting específico del orquestador"
    )

    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls para los workers del orquestador"
    )

    enable_access_validation: bool = Field(
        True,
        description="Habilitar validación de acceso tenant->agent"
    )
    validation_cache_ttl: int = Field(
        300,
        description="TTL del cache de validaciones (segundos)"
    )

    required_headers: List[str] = Field(
        default_factory=lambda: ["X-Tenant-ID", "X-Agent-ID", "X-Session-ID"],
        description="Headers requeridos para requests entrantes"
    )

    enable_performance_tracking: bool = Field(
        True,
        description="Habilitar tracking de performance para operaciones clave"
    )
