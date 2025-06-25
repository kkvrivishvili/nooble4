"""
Configuración específica para el Query Service.
"""
from typing import Dict, Any, List
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ..base_settings import CommonAppSettings

class QueryServiceSettings(CommonAppSettings):
    """
    Configuración específica para Query Service.
    Hereda de CommonAppSettings y añade/sobrescribe configuraciones.
    """
    model_config = SettingsConfigDict(extra='ignore', env_file='.env', env_prefix='QUERY_')
    
    # Domain específico para colas
    domain_name: str = Field(default="query", description="Dominio del servicio para colas y logging")
        
    # Embedding Service Configuration
    embedding_service_timeout: int = Field(default=30, description="Timeout para comunicación con Embedding Service")
    
    # Search Settings
    search_timeout_seconds: int = Field(default=10, description="Timeout para búsquedas vectoriales")

    # Worker Settings
    worker_count: int = Field(default=2, description="Número de workers para procesar queries")
    