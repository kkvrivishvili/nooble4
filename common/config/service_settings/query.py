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
    
    # Groq API Settings
    groq_api_key: str = Field(..., description="API Key para Groq (usar variable de entorno QUERY_GROQ_API_KEY)")
    
    # LLM Operational Settings ( esta configuracion se debe eliminar porque esta en query_config.py)
    groq_max_retries: int = Field(default=3, description="Número de reintentos del cliente Groq")

    # Embedding Service Configuration
    embedding_service_timeout: int = Field(default=30, description="Timeout para comunicación con Embedding Service")
    
    # Search Settings
    search_timeout_seconds: int = Field(default=10, description="Timeout para búsquedas vectoriales")

    # Worker Settings
    worker_count: int = Field(default=2, description="Número de workers para procesar queries")
    