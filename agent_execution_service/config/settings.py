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
    
    # Worker configuration
    worker_count: int = Field(
        default=2,
        gt=0,
        description="Número de workers para procesar acciones"
    )
    
    # Service info
    service_version: str = Field(default="2.0.0")