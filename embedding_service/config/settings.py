"""
Configuración del Embedding Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config.service_settings import EmbeddingServiceSettings

# La constante SUPPORTED_OPENAI_MODELS_INFO y las enums EmbeddingProviders, EncodingFormats
# ahora residen en refactorizado.common.config.service_settings.embedding
# Si se necesitan aquí, deben importarse desde allí o desde constants.py si se mueven allí.

@lru_cache()
def get_settings() -> EmbeddingServiceSettings:
    """
    Retorna la instancia de configuración para Embedding Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase EmbeddingServiceSettings (importada) se encarga de la carga desde el entorno
    con el prefijo EMBEDDING_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings, de la cual hereda EmbeddingServiceSettings)
    debe ser provisto vía variable de entorno (ej. EMBEDDING_SERVICE_NAME="embedding-service").
    Las API keys (openai_api_key, azure_openai_api_key, cohere_api_key) deben configurarse como variables de entorno
    con el prefijo EMBEDDING_ (ej. EMBEDDING_OPENAI_API_KEY).
    """
    return EmbeddingServiceSettings()
