"""
Configuración específica para el Query Service.
"""
from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from ..base_settings import CommonAppSettings

class QueryServiceSettings(CommonAppSettings):
    """
    Configuración específica para Query Service.
    Hereda de CommonAppSettings y añade/sobrescribe configuraciones.
    """
    model_config = SettingsConfigDict(extra='ignore', env_file='.env', env_prefix='QUERY_')

    # service_name, environment, log_level, redis_url, database_url, http_timeout_seconds son heredados de CommonAppSettings.

    service_name: str = Field("query_service", description="Nombre del servicio query.")
    service_version: str = Field("1.0.0", description="Versión del servicio")
    
    # Domain específico para colas
    domain_name: str = Field(default="query", description="Dominio del servicio para colas y logging")
        
    # Embedding Service Configuration
    embedding_service_timeout: int = Field(default=30, description="Timeout para comunicación con Embedding Service")
    
    # Worker Settings
    worker_count: int = Field(default=5,description="Número de workers para procesar queries")
    worker_sleep_seconds: float = Field(1.0, description="Tiempo de espera entre polls para los workers de ejecución")

    