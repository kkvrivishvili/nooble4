"""
Configuración específica para el Query Service.
"""
from typing import Dict, Any
from pydantic import Field
from pydantic_settings import SettingsConfigDict # BaseSettings se importa desde ..base_settings
from ..base_settings import CommonAppSettings

class QueryServiceSettings(CommonAppSettings):
    """
    Configuración específica para Query Service.
    Hereda de CommonAppSettings y añade/sobrescribe configuraciones.
    """
    # Domain específico para colas, sobrescribe el de CommonAppSettings si es necesario
    # o se puede quitar si el de CommonAppSettings es suficiente.
    # Por ahora, lo mantenemos para especificidad del servicio.
    domain_name: str = Field(default="query", description="Dominio del servicio para colas y logging")

    # Redis y colas específicas del Query Service
    # redis_url ya está en CommonAppSettings
    process_query_queue_segment: str = Field(default="process_query", description="Segmento específico para la cola de acciones de procesamiento de consultas (ej. 'process_query' en 'servicio:process_query:actions')")
    
    # Configuración de colas de callback (hacia dónde responde el QS)
    # Esto podría ser más genérico si el QS responde a múltiples servicios.
    # Por ahora, se asume que podría responder a 'execution' u otros.
    callback_queue_prefix: str = Field(
        default="execution", 
        description="Prefijo para colas de callback hacia servicios solicitantes (ej. Execution Service)"
    )
    
    # LLM Settings
    groq_api_key: str = Field(default="", description="API Key para Groq (usar variable de entorno QUERY_GROQ_API_KEY)")
    default_llm_model: str = Field(default="llama3-8b-8192", description="Modelo LLM por defecto para las consultas")
    llm_temperature: float = Field(default=0.3, description="Temperatura para la generación del LLM")
    llm_max_tokens: int = Field(default=1024, description="Máximo número de tokens a generar por el LLM")
    llm_timeout_seconds: int = Field(default=30, description="Timeout para las llamadas al LLM en segundos")
    llm_top_p: float = Field(default=1.0, description="Parámetro Top P para el LLM")
    llm_n: int = Field(default=1, description="Número de completaciones a generar por el LLM")
    
    # Vector Store Configuration
    vector_db_url: str = Field(default="http://localhost:8006", description="URL del servicio de base de datos vectorial") # Ejemplo: Qdrant, Weaviate
    similarity_threshold: float = Field(default=0.7, description="Umbral de similitud mínimo para considerar un resultado relevante")
    default_top_k: int = Field(default=5, description="Número de resultados (chunks) a recuperar por defecto de la base de datos vectorial")
    
    # Cache Settings
    search_cache_ttl: int = Field(
        default=300, 
        description="TTL (Time To Live) para el caché de resultados de búsqueda, en segundos"
    )
    collection_config_cache_ttl: int = Field(
        default=600, 
        description="TTL para el caché de configuraciones de colección (ej. de Agent Management), en segundos"
    )
    
    # Timeouts y reintentos para dependencias externas (excluyendo LLM que tiene su propia config)
    # http_timeout_seconds ya está en CommonAppSettings, se puede usar ese o sobrescribir.
    # max_retries ya está en CommonAppSettings.
    
    # Configuración específica de reintentos para llamadas al LLM
    llm_retry_attempts: int = Field(default=3, description="Número de intentos de reintento para llamadas al LLM")
    llm_retry_min_seconds: int = Field(default=1, description="Tiempo mínimo de espera base para reintentos al LLM, en segundos")
    llm_retry_max_seconds: int = Field(default=10, description="Tiempo máximo de espera para un reintento al LLM, en segundos")
    llm_retry_multiplier: float = Field(default=1.0, description="Factor multiplicador para el backoff exponencial en reintentos al LLM")
    
    # Worker configuración (worker_sleep_seconds ya está en CommonAppSettings)
    
    # Performance tracking
    enable_query_tracking: bool = Field(
        default=True, 
        description="Habilitar el seguimiento de métricas de rendimiento para las consultas"
    )
    
    model_config = SettingsConfigDict(extra='ignore', env_file='.env', env_prefix='QUERY_')
