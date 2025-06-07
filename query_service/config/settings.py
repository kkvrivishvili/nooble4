"""
Configuración para Query Service.
"""

import os
from typing import Dict, Any, Optional
from functools import lru_cache

from pydantic import BaseSettings
from common.config import CommonSettings

class QueryServiceSettings(CommonSettings):
    """
    Configuración específica para Query Service.
    """
    # Información del servicio
    service_name: str = "query-service"
    service_version: str = "1.0.0"
    
    # Redis y colas
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    query_actions_queue_prefix: str = os.getenv("QUERY_ACTIONS_QUEUE_PREFIX", "query")
    
    # LLM Settings
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    default_llm_model: str = os.getenv("DEFAULT_LLM_MODEL", "llama3-8b-8192")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_top_p: float = float(os.getenv("LLM_TOP_P", "1.0"))
    llm_n: int = int(os.getenv("LLM_N", "1"))
    
    # Vector Store
    vector_db_url: str = os.getenv("VECTOR_DB_URL", "http://localhost:8006")
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    default_top_k: int = int(os.getenv("DEFAULT_TOP_K", "5"))
    
    # Tiemouts y reintentos
    http_timeout_seconds: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    
    # Configuración específica de retry para LLM
    llm_retry_attempts: int = int(os.getenv("LLM_RETRY_ATTEMPTS", "3"))
    llm_retry_min_seconds: int = int(os.getenv("LLM_RETRY_MIN_SECONDS", "1"))
    llm_retry_max_seconds: int = int(os.getenv("LLM_RETRY_MAX_SECONDS", "10"))
    llm_retry_multiplier: float = float(os.getenv("LLM_RETRY_MULTIPLIER", "1.0"))
    
    # Modo de logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Modelos LLM disponibles y sus metadatos
    llm_models_info: Dict[str, Dict[str, Any]] = {
        "llama3-8b-8192": {
            "name": "Llama-3 8B",
            "context_window": 8192,
            "pricing_input": 0.20,  # Por millón de tokens
            "pricing_output": 0.80,  # Por millón de tokens
            "provider": "groq"
        },
        "llama3-70b-8192": {
            "name": "Llama-3 70B",
            "context_window": 8192,
            "pricing_input": 0.70,  # Por millón de tokens
            "pricing_output": 1.60,  # Por millón de tokens
            "provider": "groq"
        }
    }
    
    def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene información del modelo especificado o default.
        
        Args:
            model_name: Nombre del modelo o None para default
            
        Returns:
            Dict con información del modelo
        """
        model = model_name or self.default_llm_model
        return self.llm_models_info.get(model, self.llm_models_info[self.default_llm_model])


@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Obtiene configuración con caché.
    
    Returns:
        QueryServiceSettings
    """
    return QueryServiceSettings()
