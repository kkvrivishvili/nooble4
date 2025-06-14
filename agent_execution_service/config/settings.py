"""
Configuración del Agent Execution Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from common.config.service_settings import ExecutionSettings

@lru_cache()
def get_settings() -> ExecutionSettings:
    """
    Retorna la instancia de configuración para Agent Execution Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase ExecutionSettings (importada) se encarga de la carga desde el entorno
    con el prefijo AES_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings, de la cual hereda ExecutionSettings)
    debe ser provisto vía variable de entorno (ej. AES_SERVICE_NAME="agent-execution-service").
    """
    return ExecutionSettings()