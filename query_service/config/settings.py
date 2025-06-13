"""
Configuración para Query Service.
MODIFICADO: Integración con sistema de colas.
"""

import os
from typing import Dict, Any, Optional
from functools import lru_cache

from pydantic import BaseModel, Field
from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

class QueryServiceSettings(BaseSettings):
    """
    Configuración específica para Query Service.
    MODIFICADO: Integración con domain.
    """
    
    # NUEVO: Domain específico para colas
    domain_name: str = "query"
    
    # Redis y colas
    redis_url: str = Field(default="redis://localhost:6379/0", description="URL de Redis")
    query_actions_queue_prefix: str = Field(default="query", description="Prefijo de colas")
    
    # NUEVO: Configuración de colas
    callback_queue_prefix: str = Field(
        "execution",
        description="Prefijo para colas de callback hacia servicios solicitantes"
    )
    
    # LLM Settings
    groq_api_key: str = Field(default="", description="API Key para Groq")
    default_llm_model: str = Field(default="llama3-8b-8192", description="Modelo LLM default")
    llm_temperature: float = Field(default=0.3, description="Temperatura LLM")
    llm_max_tokens: int = Field(default=1024, description="Max tokens LLM")
    llm_timeout_seconds: int = Field(default=30, description="Timeout LLM")
    llm_top_p: float = Field(default=1.0, description="Top P LLM")
    llm_n: int = Field(default=1, description="N completions LLM")
    
    # Vector Store
    vector_db_url: str = Field(default="http://localhost:8006", description="URL vector DB")
    similarity_threshold: float = Field(default=0.7, description="Umbral similitud default")
    default_top_k: int = Field(default=5, description="Top K default")
    
    # NUEVO: Cache y performance
    search_cache_ttl: int = Field(
        300,
        description="TTL del cache de búsquedas (segundos)"
    )
    collection_config_cache_ttl: int = Field(
        600,
        description="TTL del cache de configuraciones de colección (segundos)"
    )
    

    
    # Timeouts y reintentos
    http_timeout_seconds: int = Field(default=15, description="Timeout HTTP")
    max_retries: int = Field(default=3, description="Max reintentos")
    
    # Configuración específica de retry para LLM
    llm_retry_attempts: int = Field(default=3, description="Intentos retry LLM")
    llm_retry_min_seconds: int = Field(default=1, description="Min segundos retry")
    llm_retry_max_seconds: int = Field(default=10, description="Max segundos retry")
    llm_retry_multiplier: float = Field(default=1.0, description="Multiplicador retry")
    
    # Worker configuración
    worker_sleep_seconds: float = Field(
        1.0,
        description="Tiempo de espera entre polls"
    )
    
    # NUEVO: Performance tracking
    enable_query_tracking: bool = Field(
        True,
        description="Habilitar tracking de métricas de consulta"
    )
    
    # Modelos LLM disponibles y sus metadatos
    llm_models_info: Dict[str, Dict[str, Any]] = Field(
        default={
            "llama3-8b-8192": {
                "name": "Llama-3 8B",
                "context_window": 8192,
                "pricing_input": 0.20,
                "pricing_output": 0.80,
                "provider": "groq"
            },
            "llama3-70b-8192": {
                "name": "Llama-3 70B",
                "context_window": 8192,
                "pricing_input": 0.70,
                "pricing_output": 1.60,
                "provider": "groq"
            }
        },
        description="Información de modelos LLM"
    )
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene información del modelo especificado o default."""
        model = model_name or self.default_llm_model
        return self.llm_models_info.get(model, self.llm_models_info[self.default_llm_model])
    

    
    class Config:
        env_prefix = "QUERY_"

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """Obtiene configuración con caché."""
    base_settings = get_base_settings("query-service")
    return QueryServiceSettings(**base_settings)