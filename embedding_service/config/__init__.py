"""
Inicialización del módulo de configuración para Embedding Service.

Exporta la clase de configuración específica del servicio (importada desde la ubicación común)
y la función de acceso a la configuración.
"""

from refactorizado.common.config.service_settings import EmbeddingServiceSettings
from .settings import get_settings

# También exportamos las constantes locales que puedan ser útiles para otros módulos del servicio
from .constants import QueueNames, EndpointPaths

# Y las enums/constantes definidas junto a EmbeddingServiceSettings si se usan frecuentemente
# Esto es opcional y depende de las necesidades de importación del servicio.
# from refactorizado.common.config.service_settings.embedding import EmbeddingProviders, EncodingFormats, SUPPORTED_OPENAI_MODELS_INFO

__all__ = [
    "EmbeddingServiceSettings",
    "get_settings",
    "QueueNames",
    "EndpointPaths",
    # Descomentar si se decide exportar directamente desde aquí:
    # "EmbeddingProviders",
    # "EncodingFormats",
    # "SUPPORTED_OPENAI_MODELS_INFO",
]
