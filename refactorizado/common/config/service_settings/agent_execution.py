"""
Definición de la configuración específica para Agent Execution Service.
"""
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings # Ajustado para la nueva ubicación

# Ajuste de ruta para importar constantes del servicio específico.
# Esto asume que la raíz del proyecto está en el PYTHONPATH
# o que la ejecución se hace desde un contexto donde esta ruta es válida.
# Si no, se podría necesitar una configuración de PYTHONPATH más explícita.
from .....agent_execution_service.config.constants import LLMProviders, DEFAULT_MODELS

class ExecutionSettings(CommonAppSettings):
    """Configuración específica para Agent Execution Service."""

    model_config = SettingsConfigDict(
        env_prefix='AES_',
        extra='ignore',
        env_file='.env'
    )

    # Campos que estaban en la antigua BaseSettings y no están en CommonAppSettings,
    # o que son específicos de ExecutionSettings.
    # service_name, environment, log_level, redis_url, database_url son heredados de CommonAppSettings.

    service_version: str = Field("1.0.0", description="Versión del servicio")
    http_timeout_seconds: int = Field(30, description="Timeout HTTP para llamadas salientes")

    # Campos específicos del Execution Service
    domain_name: str = Field("execution", description="Dominio específico para colas y lógica del servicio de ejecución.")

    # URLs de servicios externos
    embedding_service_url: str = Field("http://localhost:8001", description="URL del Embedding Service")
    query_service_url: str = Field("http://localhost:8002", description="URL del Query Service")
    conversation_service_url: str = Field("http://localhost:8004", description="URL del Conversation Service")
    agent_management_service_url: str = Field("http://localhost:8003", description="URL del Agent Management Service")

    # Configuración de LLM
    default_llm_provider: str = Field(default=LLMProviders.OPENAI, description="Proveedor LLM por defecto si no se especifica en la configuración del agente")
    default_model_name: Optional[str] = Field(default=None, description="Nombre del modelo por defecto. Si no se establece, se deriva de default_llm_provider.")

    # Límites y comportamiento de ejecución
    default_agent_type: str = Field("conversational", description="Tipo de agente por defecto")
    max_iterations: int = Field(10, description="Máximo de iteraciones para agentes")
    max_execution_time: int = Field(120, description="Tiempo máximo de ejecución (segundos)")
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

    # Performance tracking
    enable_execution_tracking: bool = Field(True, description="Habilitar tracking de métricas de ejecución")

    # Tool and Streaming settings
    tool_timeout_seconds: int = Field(30, description="Timeout for individual tool executions in seconds.")
    stream_chunk_size: int = Field(10, description="Chunk size in tokens for streaming LLM responses.")
    
    @model_validator(mode='after')
    def set_default_model_name_if_none(self) -> 'ExecutionSettings':
        if self.default_model_name is None:
            provider = self.default_llm_provider
            if provider in DEFAULT_MODELS:
                self.default_model_name = DEFAULT_MODELS[provider]
            # Si el proveedor no está en DEFAULT_MODELS o no hay un modelo para el proveedor, permanece None.
            # AgentExecutionHandler debe manejar el caso donde default_model_name sigue siendo None.
        return self
