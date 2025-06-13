"""
Configuración del Agent Execution Service.
MODIFICADO: Integración con sistema de colas por tier.
"""

from typing import Optional
from pydantic import Field, model_validator
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings
from agent_execution_service.config.constants import LLMProviders, DEFAULT_MODELS

class ExecutionSettings(BaseSettings):
    """Configuración específica para Agent Execution Service."""

    domain_name: str = "execution"

    # URLs de servicios externos
    embedding_service_url: str = Field("http://localhost:8001", description="URL del Embedding Service")
    query_service_url: str = Field("http://localhost:8002", description="URL del Query Service")
    conversation_service_url: str = Field("http://localhost:8004", description="URL del Conversation Service")
    agent_management_service_url: str = Field("http://localhost:8003", description="URL del Agent Management Service")

    # Configuración de LLM
    default_llm_provider: str = Field(default=LLMProviders.OPENAI, description="Default LLM provider if not specified in agent config")
    default_model_name: Optional[str] = Field(default=None, description="Default model name. If not set, derived from default_llm_provider.")

    # Límites y comportamiento de ejecución
    default_agent_type: str = Field("conversational", description="Tipo de agente por defecto")
    max_iterations: int = Field(10, description="Máximo de iteraciones para agentes")
    max_execution_time: int = Field(120, description="Tiempo máximo de ejecución (segundos)")
    max_tools: int = Field(10, description="Número máximo de herramientas que un agente puede usar")

    # Configuración de colas
    callback_queue_prefix: str = Field("orchestrator", description="Prefijo para colas de callback hacia orchestrator")

    # Cache de configuraciones
    agent_config_cache_ttl: int = Field(600, description="TTL del cache de configuraciones de agente (segundos)")

    # Cache de conversaciones
    conversation_cache_ttl: int = Field(1200, description="TTL del cache de historiales de conversación (segundos)")
    default_conversation_cache_limit: int = Field(40, description="Número máximo de mensajes para mantener en caché local de conversación")
    wait_for_persistence: bool = Field(False, description="Indica si se debe esperar la confirmación de persistencia al guardar mensajes")

    # Worker configuración
    worker_sleep_seconds: float = Field(1.0, description="Tiempo de espera entre polls")

    # Performance tracking
    enable_execution_tracking: bool = Field(True, description="Habilitar tracking de métricas de ejecución")
    
    @model_validator(mode='after')
    def set_default_model_name_if_none(self) -> 'ExecutionSettings':
        if self.default_model_name is None:
            provider = self.default_llm_provider
            if provider in DEFAULT_MODELS:
                self.default_model_name = DEFAULT_MODELS[provider]
            # If provider not in DEFAULT_MODELS or no model for provider, it remains None
            # AgentExecutionHandler must handle the case where default_model_name is still None.
        return self

    class Config:
        env_prefix = "EXECUTION_"

def get_settings() -> ExecutionSettings:
    """Obtiene configuración del servicio."""
    base_settings = get_base_settings("agent-execution-service")
    return ExecutionSettings(**base_settings.model_dump())