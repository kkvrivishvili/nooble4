"""
Configuración del servicio de ingestión.

Expone la configuración centralizada del servicio.
"""

from .settings import IngestionServiceSettings, get_settings
from .constants import TaskStates, DocumentTypes, EndpointPaths, VERSION

__all__ = [
    'IngestionServiceSettings',
    'get_settings',
    'TaskStates',
    'DocumentTypes',
    'EndpointPaths',
    'VERSION'
]
