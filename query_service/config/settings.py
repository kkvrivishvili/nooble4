"""
Configuración para Query Service.
"""

from functools import lru_cache
from common.config import QueryServiceSettings as CommonQueryServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict

class QueryServiceSettings(CommonQueryServiceSettings):
    """
    Configuración específica del Query Service.
    Solo mantiene configuraciones del servicio, no de los datos de operación.
    """
    
    model_config = SettingsConfigDict(
        env_prefix='QUERY_',
        extra='ignore',
        env_file='.env'
    )
    
    # Configuración del servicio
    service_name: str = Field(default="query_service")
    service_version: str = Field(default="2.0.0")
    
    # Timeouts del servicio
    search_timeout_seconds: int = Field(default=30, description="Timeout para búsquedas vectoriales")
    
    # Worker configuration
    
    # Worker configuration
    worker_count: int = Field(default=2, gt=0, description="Número de workers")

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Retorna la instancia de configuración para Query Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return QueryServiceSettings()

# Para facilitar el acceso directo
settings = get_settings()