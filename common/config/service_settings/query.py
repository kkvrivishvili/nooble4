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
    groq_api_base_url: str = Field(default="https://api.groq.com/openai/v1", description="URL base de la API de Groq")
    
    # LLM Operational Settings
    llm_timeout_seconds: int = Field(default=60, description="Timeout para las llamadas al LLM en segundos")
    groq_max_retries: int = Field(default=3, description="Número de reintentos del cliente Groq")



    
    # Embedding Service Configuration
    embedding_service_timeout: int = Field(default=30, description="Timeout para comunicación con Embedding Service")
    
    # Search Settings
    max_search_results: int = Field(default=10, description="Número máximo de resultados de búsqueda a retornar")
    search_timeout_seconds: int = Field(default=10, description="Timeout para búsquedas vectoriales")
    
    # RAG Settings
    rag_context_window: int = Field(default=4000, description="Tamaño máximo del contexto en tokens para RAG")
    rag_system_prompt_template: str = Field(
        default=(
            "Eres un asistente útil que responde preguntas basándose en el contexto proporcionado. "
            "Siempre cita la información relevante del contexto cuando sea posible. "
            "Si el contexto no contiene información suficiente para responder la pregunta, "
            "indícalo claramente. No inventes información que no esté en el contexto."
        ),
        description="Prompt de sistema por defecto para RAG"
    )
    
    # Performance Settings
    enable_query_tracking: bool = Field(default=True, description="Habilitar el seguimiento de métricas de rendimiento")
    parallel_search_enabled: bool = Field(default=True, description="Habilitar búsquedas paralelas en múltiples colecciones")
    
    # Worker Settings
    worker_count: int = Field(default=2, description="Número de workers para procesar queries")
    
    # Retry Settings para servicios externos
    max_retries: int = Field(default=3, description="Reintentos máximos para llamadas a servicios externos")
    retry_delay_seconds: float = Field(default=1.0, description="Delay base entre reintentos")
    retry_backoff_factor: float = Field(default=2.0, description="Factor de backoff para reintentos")