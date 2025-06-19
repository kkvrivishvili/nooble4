"""
Configuración específica para Agent Execution Service.
"""
from typing import Optional, Dict, Any
from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict
from common.config.base_settings import CommonAppSettings

class ExecutionServiceSettings(CommonAppSettings):

    """Configuración específica para Agent Execution Service."""

   
   # Domain específico
    domain_name: str = Field(default="execution")

    # Nombres de servicios para comunicación interna
    query_service_name: str = Field(default="query-service")
    
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
