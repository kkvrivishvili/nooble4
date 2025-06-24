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
        env_prefix='AES_',
        extra='ignore',
        env_file='.env'
    )

# Campos específicos de ExecutionSettings o que anulan valores de CommonAppSettings.
# service_name, environment, log_level, redis_url, database_url, http_timeout_seconds son heredados de CommonAppSettings.

    service_version: str = Field("1.0.0", description="Versión del servicio")

    # Campos específicos del Execution Service
    domain_name: str = Field("execution", description="Dominio específico para colas y lógica del servicio de ejecución.")

    # Límites y comportamiento de ejecución
    max_iterations: int = Field(10, description="Máximo de iteraciones para agentes")
    max_tools: int = Field(10, description="Número máximo de herramientas que un agente puede usar")

    # Configuración de colas
    callback_queue_prefix: str = Field("orchestrator", description="Prefijo para colas de callback hacia el orquestador")

    # Cache de configuraciones
    agent_config_cache_ttl: int = Field(600, description="TTL del cache de configuraciones de agente (segundos)")

    # Cache de conversaciones
    conversation_cache_ttl: int = Field(1200, description="TTL del cache de historiales de conversación (segundos)")
    default_conversation_cache_limit: int = Field(40, description="Número máximo de mensajes para mantener en caché local de conversación")
    wait_for_persistence: bool = Field(False, description="Indica si se debe esperar la confirmación de persistencia al guardar mensajes")

    # Worker configuración
    worker_sleep_seconds: float = Field(1.0, description="Tiempo de espera entre polls para los workers de ejecución")

    # Tool and Streaming settings
    tool_timeout_seconds: int = Field(30, description="Timeout for individual tool executions in seconds.")
