"""
Inicialización del módulo de configuración para Conversation Service.

Exporta la clase de configuración específica del servicio (importada desde la ubicación común)
_y la función de acceso a la configuración.
"""

from refactorizado.common.config.service_settings import ConversationSettings
from .settings import get_settings

__all__ = [
    "ConversationSettings",
    "get_settings",
]
