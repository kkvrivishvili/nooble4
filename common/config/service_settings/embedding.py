"""
Definición de la configuración específica para Embedding Service.
"""
from typing import Dict, Any, List, Optional
from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings

# --- Constantes que se usan en Settings o son informativas ---
class EmbeddingProviders(str, Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    SENTENCE_TRANSFORMERS = "sentence_transformers"

class EncodingFormats(str, Enum):
    FLOAT = "float"
    BASE64 = "base64"
    # BINARY = "binary" # Binary no es directamente soportado por Pydantic para JSON, considerar alternativas

class EmbeddingServiceSettings(CommonAppSettings):
    """Configuración específica para Embedding Service."""

    model_config = SettingsConfigDict(
        env_prefix='EMBEDDING_',
        extra='ignore',
        env_file='.env'
    )

    # --- Información del servicio ---
    # service_name, environment, log_level, redis_url, database_url son heredados de CommonAppSettings.
    domain_name: str = Field("embedding", description="Nombre de dominio para colas y lógica del servicio.")
    service_version: str = Field("1.0.0", description="Versión del servicio de embeddings.")

    # --- Configuración de Proveedores de Embeddings ---
    openai_api_key: Optional[str] = Field(None, description="API Key para OpenAI. Requerida si se usa el proveedor OpenAI.")
    azure_openai_api_key: Optional[str] = Field(None, description="API Key para Azure OpenAI. Requerida si se usa Azure OpenAI.")
    azure_openai_endpoint: Optional[str] = Field(None, description="Endpoint para Azure OpenAI. Requerido si se usa Azure OpenAI.")
    azure_openai_deployment_name: Optional[str] = Field(None, description="Nombre del deployment en Azure OpenAI.")
    cohere_api_key: Optional[str] = Field(None, description="API Key para Cohere. Requerida si se usa el proveedor Cohere.")

    default_models_by_provider: Dict[EmbeddingProviders, str] = Field(
        default_factory=lambda: {
            EmbeddingProviders.OPENAI: "text-embedding-3-large",
            EmbeddingProviders.AZURE_OPENAI: "text-embedding-ada-002", # Asegurarse que este es el nombre del deployment
            EmbeddingProviders.COHERE: "embed-english-v3.0",
            EmbeddingProviders.HUGGINGFACE: "sentence-transformers/all-mpnet-base-v2",
            EmbeddingProviders.SENTENCE_TRANSFORMERS: "all-mpnet-base-v2"
        },
        description="Modelos de embedding por defecto para cada proveedor."
    )

    default_dimensions_by_model: Dict[str, int] = Field(
        default_factory=lambda: {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
            "embed-english-v3.0": 1024, # Cohere
            "all-mpnet-base-v2": 768    # Sentence Transformers
        },
        description="Dimensiones por defecto para modelos conocidos. Usado como fallback."
    )
    
    preferred_dimensions: Optional[int] = Field(
        None,  # None indica usar dimensiones default del modelo
        description="Dimensiones preferidas para embeddings (None = usar default del modelo). Algunos modelos permiten especificar dimensiones."
    )
    encoding_format: EncodingFormats = Field(
        EncodingFormats.FLOAT,
        description="Formato de codificación de embeddings (float o base64)."
    )

    # --- Configuración de Colas y Workers ---
    callback_queue_prefix: str = Field("embedding", description="Prefijo para colas de callback.")
    worker_sleep_seconds: float = Field(0.1, description="Tiempo de espera para workers de procesamiento.")

    # --- Límites Operacionales y de Procesamiento por Lotes ---
    default_batch_size: int = Field(50, description="Tamaño de lote por defecto para procesamiento de embeddings.")
    default_max_text_length: int = Field(8192, description="Longitud máxima de texto por defecto (en tokens o caracteres según el modelo).")
    default_truncation_strategy: str = Field("end", description="Estrategia de truncamiento por defecto si el texto excede la longitud máxima.")

    # --- Configuración de Caché ---
    embedding_cache_enabled: bool = Field(True, description="Habilitar la caché de embeddings.")
    cache_ttl_seconds: int = Field(86400, description="TTL para la caché de embeddings (segundos). 24 horas por defecto.")
    cache_max_size: int = Field(10000, description="Número máximo de entradas en la caché de embeddings.")

    # --- Configuración de Reintentos y Timeouts para Proveedores Externos ---
    provider_timeout_seconds: int = Field(30, description="Timeout en segundos para llamadas a proveedores de embeddings.")
    provider_max_retries: int = Field(3, description="Número máximo de reintentos para llamadas a proveedores.")
    provider_retry_backoff_factor: float = Field(0.5, description="Factor de backoff para reintentos.")
    provider_retry_statuses: List[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504],
        description="Códigos de estado HTTP que activarán un reintento."
    )

    # --- Métricas y Tracking ---
    enable_embedding_tracking: bool = Field(True, description="Habilitar tracking de métricas de uso de embeddings.")
    slow_embed_threshold_ms: int = Field(500, description="Umbral en milisegundos para considerar una generación de embedding como lenta.")

    # --- Validadores ---
    @field_validator('encoding_format', mode='before')
    @classmethod
    def _validate_encoding_format(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.lower()
        return v

    # Podrían añadirse validadores para asegurar que las API keys están presentes si se usan ciertos proveedores,
    # o que los modelos por defecto son válidos para los proveedores seleccionados.
