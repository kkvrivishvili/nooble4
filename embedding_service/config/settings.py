"""
Configuración del servicio de embeddings.
Configuraciones esenciales para OpenAI y el servicio.
"""

from typing import Dict, Any
from pydantic import Field

from common.config import Settings as BaseSettings
from common.config import get_service_settings as get_base_settings

# Modelos de OpenAI soportados
OPENAI_MODELS = {
    "text-embedding-3-small": {
        "dimensions": 1536,
        "max_tokens": 8191,
        "description": "Modelo de uso general con excelente balance costo/rendimiento"
    },
    "text-embedding-3-large": {
        "dimensions": 3072,
        "max_tokens": 8191,
        "description": "Modelo de alta precisión para tareas complejas"
    },
    "text-embedding-ada-002": {
        "dimensions": 1536,
        "max_tokens": 8191,
        "description": "Compatibilidad con sistemas legacy"
    }
}

class EmbeddingServiceSettings(BaseSettings):
    """Configuración para el servicio de embeddings."""
    
    # Información del servicio
    domain_name: str = Field("embedding", description="Nombre de dominio para el servicio")
    
    # OpenAI
    openai_api_key: str = Field(..., description="API Key para OpenAI")
    default_embedding_model: str = Field(
        "text-embedding-3-small",
        description="Modelo de embedding predeterminado"
    )
    preferred_dimensions: int = Field(
        0,  # 0 indica usar dimensiones default del modelo
        description="Dimensiones preferidas para embeddings (0 = usar default del modelo)"
    )
    encoding_format: str = Field(
        "float",
        description="Formato de codificación de embeddings (float o base64)"
    )
    
    # Límites operacionales
    max_texts_per_request: int = Field(100, description="Número máximo de textos por request")
    max_text_length: int = Field(8000, description="Longitud máxima de texto en caracteres")
    max_batch_size: int = Field(100, description="Número máximo de textos por batch")
    max_requests_per_hour: int = Field(0, description="Máximo de requests por hora (0 para deshabilitado)")

    # Caché y métricas
    enable_embedding_tracking: bool = Field(True, description="Habilitar tracking de métricas de embeddings")
    embedding_cache_enabled: bool = Field(True, description="Habilitar la caché de embeddings")
    embedding_cache_ttl: int = Field(3600, description="Tiempo de vida en segundos para la caché de embeddings")
    
    # Timeouts
    openai_timeout_seconds: int = Field(30, description="Timeout para llamadas a OpenAI")
    
    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "EMBEDDING_"

def get_settings() -> EmbeddingServiceSettings:
    """Obtiene la configuración del servicio."""
    base_settings = get_base_settings("embedding-service")
    
    # Completar con valores específicos de OpenAI
    settings_dict = base_settings.copy()
    settings_dict.update({
        # IMPORTANTE: Esta API key debe reemplazarse por una variable de entorno en producción
        # TODO: Cambiar a os.getenv("EMBEDDING_OPENAI_API_KEY") cuando se implemente el manejo de .env
        "openai_api_key": "sk-your-actual-openai-api-key-here", # Temporalmente hardcodeada, reemplazar en producción
        "default_embedding_model": "text-embedding-3-small",
        "preferred_dimensions": 0,  # 0 = usar dimensiones default del modelo
        "encoding_format": "float",
        "max_batch_size": 100,
        "max_text_length": 8000,
        "openai_timeout_seconds": 30
    })
    
    return EmbeddingServiceSettings(**settings_dict)
