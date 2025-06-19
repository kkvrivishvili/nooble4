"""
Configuración específica para Agent Execution Service.
"""
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from common.config.base_settings import CommonAppSettings


class ExecutionServiceSettings(CommonAppSettings):
    """Configuración específica para Agent Execution Service."""

    model_config = SettingsConfigDict(
        env_prefix='AES_',
        extra='ignore',
        env_file='.env'
    )

    # Domain específico
    domain_name: str = Field(default="execution")
    
    # Timeouts
    query_timeout_seconds: int = Field(
        default=30, 
        description="Timeout para operaciones con Query Service"
    )
    tool_execution_timeout: int = Field(
        default=30,
        description="Timeout para ejecución de herramientas"
    )
    
    # ReAct configuration
    max_react_iterations: int = Field(
        default=10,
        gt=0,
        le=20,
        description="Máximo de iteraciones para el loop ReAct"
    )
    
    # Worker configuration
    worker_count: int = Field(
        default=2,
        gt=0,
        description="Número de workers para procesar acciones"
    )
    
    # Service info
    service_version: str = Field(default="2.0.0")