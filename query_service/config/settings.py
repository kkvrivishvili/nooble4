"""
Configuración para Query Service.

Este módulo carga la configuración del servicio usando QueryServiceSettings
definido en common.config.service_settings.query
"""

from functools import lru_cache
from common.config import QueryServiceSettings

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Retorna la instancia de configuración para Query Service.
    Usa lru_cache para asegurar que solo se crea una instancia.
    """
    return QueryServiceSettings()

# Para facilitar el acceso directo
settings = get_settings()