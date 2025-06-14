"""
Configuración del Agent Orchestrator Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config.service_settings import OrchestratorSettings

@lru_cache()
def get_settings() -> OrchestratorSettings:
    """
    Retorna la instancia de configuración para Agent Orchestrator Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase OrchestratorSettings (importada) se encarga de la carga desde el entorno
    con el prefijo AOS_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings, de la cual hereda OrchestratorSettings)
    debe ser provisto vía variable de entorno (ej. AOS_SERVICE_NAME="agent-orchestrator-service").
    """
    return OrchestratorSettings()