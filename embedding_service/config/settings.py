"""
Configuración del servicio de embeddings.
Configuraciones esenciales para OpenAI y el servicio.
"""

from typing import Dict
from pydantic import Field

from common.config import Settings as BaseSettings
from common.config import get_service_settings

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
    max_batch_size: int = Field(100, description="Número máximo de textos por batch")
    max_text_length: int = Field(8000, description="Longitud máxima de texto en caracteres")
    
    # Timeouts
    openai_timeout_seconds: int = Field(30, description="Timeout para llamadas a OpenAI")
    
    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "EMBEDDING_"

def get_settings() -> EmbeddingServiceSettings:
    """Obtiene la configuración del servicio."""
    base_settings = get_service_settings("embedding-service")
    
    # Completar con valores específicos de OpenAI
    settings_dict = base_settings.copy()
    settings_dict.update({
        "openai_api_key": "sk-", # En producción se obtiene de variables de entorno
        "default_embedding_model": "text-embedding-3-small",
        "preferred_dimensions": 0,  # 0 = usar dimensiones default del modelo
        "encoding_format": "float",
        "max_batch_size": 100,
        "max_text_length": 8000,
        "openai_timeout_seconds": 30
    })
    
    return EmbeddingServiceSettings(**settings_dict)
