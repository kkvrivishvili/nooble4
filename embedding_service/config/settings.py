"""
Configuración para Embedding Service.

Este módulo carga la configuración del servicio usando EmbeddingServiceSettings
definido en common.config.service_settings.embedding
"""

from functools import lru_cache
from common.config import EmbeddingServiceSettings

@lru_cache()
def get_settings() -> EmbeddingServiceSettings:
    """
    Retorna la instancia de configuración para Embedding Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return EmbeddingServiceSettings()

# Para facilitar el acceso directo
settings = get_settings()