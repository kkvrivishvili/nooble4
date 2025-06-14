"""
Configuración del Conversation Service.
Importa la configuración específica del servicio desde la ubicación común centralizada.
"""
from functools import lru_cache

# Importa la clase de settings específica del servicio desde la ubicación común centralizada
from refactorizado.common.config.service_settings import ConversationSettings

@lru_cache()
def get_settings() -> ConversationSettings:
    """
    Retorna la instancia de configuración para Conversation Service.
    Utiliza lru_cache para retornar la misma instancia una vez cargada.
    La clase ConversationSettings (importada) se encarga de la carga desde el entorno
    con el prefijo CONVERSATION_ y el archivo .env.
    El campo 'service_name' (requerido por CommonAppSettings, de la cual hereda ConversationSettings)
    debe ser provisto vía variable de entorno (ej. CONVERSATION_SERVICE_NAME="conversation-service").
    """
    return ConversationSettings()
