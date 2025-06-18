"""
Configuración del Ingestion Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config import IngestionServiceSettings

# Las enums como ChunkingStrategies, StorageTypes, etc., ahora residen en
# refactorizado.common.config.service_settings.ingestion.py o en constants.py local.

@lru_cache()
def get_settings() -> IngestionServiceSettings:
    """
    Retorna la instancia de configuración para Ingestion Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase IngestionServiceSettings (importada) se encarga de la carga desde el entorno
    con el prefijo INGESTION_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings) debe ser provisto vía
    variable de entorno (ej. INGESTION_SERVICE_NAME="ingestion-service").
    """
    return IngestionServiceSettings()
