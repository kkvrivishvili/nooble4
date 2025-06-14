"""
Inicialización del módulo de configuración común.

Este módulo proporciona la clase base CommonAppSettings y también re-exporta
las clases de configuración específicas de cada servicio desde el submódulo `service_settings`.

Esto permite importar configuraciones así:
from refactorizado.common.config import CommonAppSettings, AgentOrchestratorSettings, EmbeddingServiceSettings, IngestionServiceSettings
"""

from .base_settings import CommonAppSettings, get_service_settings
from .service_settings import (
    AgentManagementSettings,
    OrchestratorSettings,       # Corrected name based on its definition
    ExecutionSettings,         # Corrected name based on its definition
    ConversationSettings,
    EmbeddingServiceSettings,
    IngestionServiceSettings,
    QueryServiceSettings
)

__all__ = [
    "CommonAppSettings",
    "get_service_settings",
    "AgentManagementSettings",
    "OrchestratorSettings",
    "ExecutionSettings",
    "ConversationSettings",
    "EmbeddingServiceSettings",
    "IngestionServiceSettings",
    "QueryServiceSettings",
]
