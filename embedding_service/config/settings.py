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
    max_batch_size: int = Field(100, description="Número máximo de textos por batch")
    max_text_length: int = Field(8000, description="Longitud máxima de texto en caracteres")
    
    # Caché y métricas
    enable_embedding_tracking: bool = Field(True, description="Habilitar tracking de métricas de embeddings")
    embedding_cache_ttl: int = Field(3600, description="Tiempo de vida en segundos para la caché de embeddings")
    
    # Timeouts
    openai_timeout_seconds: int = Field(30, description="Timeout para llamadas a OpenAI")
    
    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "EMBEDDING_"
        
    def get_tier_limits(self, tier: str) -> Dict[str, Any]:
        """Obtiene límites y configuraciones específicas por tier.

        Args:
            tier: Nivel del tenant (free, basic, professional, enterprise)

        Returns:
            Diccionario de configuraciones y límites
        """
        # Configuración base para todos los tiers
        base_limits = {
            "cache_enabled": True,
            "max_batch_size": self.max_batch_size,
            "max_text_length": self.max_text_length,
            "allowed_models": list(OPENAI_MODELS.keys()),
        }
        
        # Configuraciones específicas por tier
        tier_specific = {
            "free": {
                "max_texts_per_request": 10,
                "max_text_length": 2000,
                "daily_quota": 100,
                "cache_enabled": True,
                "allowed_models": ["text-embedding-3-small"],
            },
            "basic": {
                "max_texts_per_request": 25,
                "max_text_length": 4000,
                "daily_quota": 500,
                "cache_enabled": True,
                "allowed_models": ["text-embedding-3-small"],
            },
            "professional": {
                "max_texts_per_request": 50,
                "max_text_length": 8000,
                "daily_quota": 2000,
                "cache_enabled": True,
                "allowed_models": ["text-embedding-3-small", "text-embedding-3-large"],
            },
            "enterprise": {
                "max_texts_per_request": 100,
                "max_text_length": 8000,
                "daily_quota": 10000,
                "cache_enabled": True,
                "allowed_models": ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
            },
        }
        
        # Usar tier específico o default a "free"
        tier_limits = tier_specific.get(tier, tier_specific["free"])
        
        # Combinar con límites base
        return {**base_limits, **tier_limits}

def get_settings() -> EmbeddingServiceSettings:
    """Obtiene la configuración del servicio."""
    base_settings = get_base_settings("embedding-service")
    
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
