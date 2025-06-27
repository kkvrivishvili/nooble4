"""
Definición de la configuración específica para Agent Execution Service.
"""
from typing import Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings # Ajustado para la nueva ubicación

class ExecutionServiceSettings(CommonAppSettings):
    """Configuración específica para Agent Execution Service."""

    model_config = SettingsConfigDict(
        extra='ignore'
    )

# Campos específicos de ExecutionSettings o que anulan valores de CommonAppSettings.
# service_name, environment, log_level, redis_url, database_url, http_timeout_seconds son heredados de CommonAppSettings.

    service_name: str = Field("agent_execution_service", description="Nombre del servicio de ejecución de agentes.")
    service_version: str = Field("1.0.0", description="Versión del servicio")

    # Campos específicos del Execution Service
    domain_name: str = Field("execution", description="Dominio específico para colas y lógica del servicio de ejecución.")

    # Configuración de colas
    callback_queue_prefix: str = Field("orchestrator", description="Prefijo para colas de callback hacia el orquestador")

    # Cache de configuraciones
    user_config_cache_ttl: int = Field(600, description="TTL del cache de configuraciones de usuario (segundos)")

    # Worker configuración
    worker_count: int = Field(default=5, description="Número de workers para procesar ejecuciones de agentes")
    worker_sleep_seconds: float = Field(1.0, description="Tiempo de espera entre polls para los workers de ejecución")
    
    # Timeouts para servicios externos
    query_timeout_seconds: int = Field(60, description="Timeout para peticiones al Query Service (segundos)")
