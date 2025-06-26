"""
Definición de la configuración específica para Embedding Service.
"""
from typing import List, Optional, Dict
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
   
    # --- Configuración de Colas y Workers ---
    worker_count: int = Field(default=1, description="Número de workers para procesar embeddings.")
    callback_queue_prefix: str = Field("embedding", description="Prefijo para colas de callback.")
    worker_sleep_seconds: float = Field(0.1, description="Tiempo de espera para workers de procesamiento.")

    # --- Configuración del Cliente OpenAI ---
    openai_timeout_seconds: int = Field(default=30, description="Timeout en segundos para las llamadas a la API de OpenAI.")
    openai_max_retries: int = Field(default=3, description="Número máximo de reintentos para las llamadas a la API de OpenAI.")


    