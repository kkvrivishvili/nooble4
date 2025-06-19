"""
Configuración específica para Agent Execution Service.
"""
from typing import Optional, Dict, Any
from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict
from common.config.base_settings import CommonAppSettings

class ExecutionServiceSettings(CommonAppSettings):
    """Configuración específica para Agent Execution Service."""

    model_config = SettingsConfigDict(
        env_prefix='AES_',
        extra='ignore',
        env_file='.env'
    )

    # Información del servicio (override de CommonAppSettings)
    service_name: str = Field(default="agent-execution-service") # Consistent naming with hyphens
    service_version: str = Field(default="1.0.0")
    
    # Domain específico
    domain_name: str = Field(default="execution")

    # Nombres de servicios para comunicación interna
    query_service_name: str = Field(default="query-service")

    # URLs de servicios externos
    query_service_url: str = Field(
        default="http://localhost:8002", 
        description="URL del Query Service para RAG (será obsoleto con Redis)"
    )
    conversation_service_url: str = Field(
        default="http://localhost:8004", 
        description="URL del Conversation Service (será obsoleto con Redis)"
    )
    agent_management_service_url: str = Field(
        default="http://localhost:8003", 
        description="URL del Agent Management Service (será obsoleto con Redis)"
    )

    # Configuración de LLM por defecto
    default_llm_provider: str = Field(default="groq")
    default_model_name: str = Field(default="llama-3.3-70b-versatile")
    
    # API Keys para LLMs
    openai_api_key: Optional[str] = Field(None)
    groq_api_key: Optional[str] = Field(None)
    anthropic_api_key: Optional[str] = Field(None)

    # Timeouts
    query_client_timeout_seconds: int = Field(default=30, description="Default timeout in seconds for QueryClient Redis operations")

    # Límites de ejecución
    max_iterations: int = Field(default=10, gt=0)
    max_execution_time: int = Field(default=120, gt=0)
    max_tools: int = Field(default=10, gt=0)

    # Configuración de workers
    worker_count: int = Field(default=2, gt=0)
    
    # Timeouts específicos
    llm_timeout_seconds: int = Field(default=60, gt=0)
    tool_timeout_seconds: int = Field(default=30, gt=0)
    
    # Configuración de streaming
    enable_streaming: bool = Field(default=False)
    stream_chunk_size: int = Field(default=1024, gt=0)

    @model_validator(mode='after')
    def validate_api_keys(self) -> 'ExecutionServiceSettings':
        """Valida que al menos una API key esté configurada."""
        if not any([self.openai_api_key, self.groq_api_key, self.anthropic_api_key]):
            self._logger.warning("Ninguna API key de LLM configurada. El servicio puede no funcionar correctamente.")
        return self