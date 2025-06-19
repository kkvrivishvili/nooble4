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
    groq_api_key: str = Field(default="", description="API Key para Groq (usar variable de entorno QUERY_GROQ_API_KEY)")
    groq_api_base_url: str = Field(default="https://api.groq.com/openai/v1", description="URL base de la API de Groq")
    
    # LLM Settings por defecto
    default_llm_model: str = Field(default="llama-3.3-70b-versatile", description="Modelo LLM por defecto para las consultas")
    llm_temperature: float = Field(default=0.3, description="Temperatura para la generación del LLM")
    llm_max_tokens: int = Field(default=1024, description="Máximo número de tokens a generar por el LLM")
    llm_timeout_seconds: int = Field(default=60, description="Timeout para las llamadas al LLM en segundos")
    groq_max_retries: int = Field(default=3, description="Número de reintentos del cliente Groq")
    llm_top_p: float = Field(default=1.0, description="Parámetro Top P para el LLM")
    llm_frequency_penalty: float = Field(default=0.0, description="Penalización de frecuencia para el LLM")
    llm_presence_penalty: float = Field(default=0.0, description="Penalización de presencia para el LLM")
    llm_default_stop_sequences: Optional[List[str]] = Field(default=None, description="Default stop sequences for LLM generation")
    
    # Modelos disponibles
    available_llm_models: List[str] = Field(
        default_factory=lambda: [
            "llama-3.3-70b-versatile",
            "llama3-70b-8192", 
            "llama3-8b-8192",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "llama-guard-3-8b"
        ],
        description="Modelos LLM disponibles en Groq"
    )
    
    # Vector Store Configuration
    vector_db_url: str = Field(default="http://localhost:8006", description="URL del servicio de base de datos vectorial")
    similarity_threshold: float = Field(default=0.7, description="Umbral de similitud mínimo para considerar un resultado relevante")
    default_top_k: int = Field(default=5, description="Número de resultados (chunks) a recuperar por defecto de la base de datos vectorial")
    
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