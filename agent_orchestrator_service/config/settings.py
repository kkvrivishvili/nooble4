"""
Configuración del Agent Orchestrator Service.
Actualizado para incluir nuevas configuraciones.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio
from common.config.service_settings import OrchestratorSettings

@lru_cache()
def get_settings() -> OrchestratorSettings:
    """
    Retorna la instancia de configuración para Agent Orchestrator Service.
    Actualizada para nuevas funcionalidades.
    """
    return OrchestratorSettings()