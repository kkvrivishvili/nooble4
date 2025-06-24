"""
Definición de la configuración específica para Embedding Service.
"""
from typing import List, Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from ..base_settings import CommonAppSettings


class EmbeddingServiceSettings(CommonAppSettings):
    """
    Configuración específica para Embedding Service.
    Define parámetros operacionales y de infraestructura. Los parámetros de negocio
    (modelo, dimensiones, etc.) se reciben por solicitud en el objeto RAGConfig.
    """

    model_config = SettingsConfigDict(
        env_prefix='EMBEDDING_',
        extra='ignore',
        env_file='.env'
    )

    # --- Información del servicio ---
    domain_name: str = Field("embedding", description="Nombre de dominio para colas y lógica del servicio.")
    service_version: str = Field("1.0.0", description="Versión del servicio de embeddings.")

    # --- Configuración de Proveedores de Embeddings (Secretos y URLs) ---
    openai_api_key: Optional[str] = Field(None, description="API Key para OpenAI. Requerida si se usa el proveedor OpenAI.")
    openai_base_url: Optional[str] = Field(None, description="URL base para la API de OpenAI (opcional, útil para proxies o APIs compatibles).")
    
    # --- Configuración de Colas y Workers ---
    worker_count: int = Field(default=2, description="Número de workers para procesar embeddings.")
    callback_queue_prefix: str = Field("embedding", description="Prefijo para colas de callback.")
    worker_sleep_seconds: float = Field(0.1, description="Tiempo de espera para workers de procesamiento.")

    # --- Límites Operacionales y de Procesamiento por Lotes ---
    default_batch_size: int = Field(50, description="Tamaño de lote por defecto para procesamiento de embeddings.")
    default_max_text_length: int = Field(8192, description="Longitud máxima de texto por defecto (en tokens o caracteres según el modelo).")
    default_truncation_strategy: str = Field("end", description="Estrategia de truncamiento por defecto si el texto excede la longitud máxima.")

    # --- Métricas y Tracking ---
    enable_embedding_tracking: bool = Field(True, description="Habilitar tracking de métricas de uso de embeddings.")
    slow_embed_threshold_ms: int = Field(500, description="Umbral en milisegundos para considerar una generación de embedding como lenta.")
