"""
Módulo de Handlers Comunes (`refactorizado.common.handlers`)

Este paquete proporciona clases base abstractas para diferentes tipos de handlers
utilizados en el sistema, facilitando la creación de lógica de procesamiento
de acciones, callbacks y contextos de manera estandarizada.
"""

from .base_handler import BaseHandler
from .base_callback_handler import BaseCallbackHandler
from .base_context_handler import BaseContextHandler

__all__ = [
    "BaseHandler",
    "BaseActionHandler",
    "BaseCallbackHandler",
    "BaseContextHandler",
]
