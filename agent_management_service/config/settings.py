"""
Configuración del Agent Management Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config.service_settings import AgentManagementSettings

@lru_cache()
def get_settings() -> AgentManagementSettings:
    """
    Retorna la instancia de configuración para Agent Management Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase AgentManagementSettings (importada) se encarga de la carga desde el entorno
    con el prefijo AMS_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings, de la cual hereda AgentManagementSettings)
    debe ser provisto vía variable de entorno (ej. AMS_SERVICE_NAME="agent-management-service").
    """
    return AgentManagementSettings()
