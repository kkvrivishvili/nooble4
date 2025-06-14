"""
Configuración para Query Service.

Este módulo carga la configuración específica del Query Service,
utilizando la estructura centralizada de 'refactorizado.common.config'.
"""

from functools import lru_cache
from refactorizado.common.config.service_settings.query import QueryServiceSettings
from refactorizado.common.config.settings import get_service_settings

@lru_cache()
def get_settings() -> QueryServiceSettings:
    """
    Obtiene la configuración para el Query Service.

    Utiliza la función centralizada get_service_settings para cargar la clase
    QueryServiceSettings con el prefijo de entorno y nombre de servicio adecuados.
    La caché (lru_cache) asegura que la configuración solo se carga una vez.
    """
    return get_service_settings(QueryServiceSettings, "query")

# Para permitir una fácil verificación o uso directo si es necesario en algún script
# o prueba fuera del ciclo de vida normal de la aplicación FastAPI.
settings = get_settings()