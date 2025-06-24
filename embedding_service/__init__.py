"""
Embedding Service - Servicio de generación de embeddings.

Este servicio maneja la generación de embeddings vectoriales
para textos usando la API de OpenAI y otros proveedores.
"""

__version__ = "1.0.0"

from .clients import OpenAIClient
from common.config.service_settings import EmbeddingServiceSettings
from .handlers import OpenAIHandler, ValidationHandler
from .models import (
    EmbeddingBatchPayload,
    EmbeddingBatchResult
)
from .services import EmbeddingService
from .workers import EmbeddingWorker

# Importar modelos comunes que el servicio expone
from common.models.chat_models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingModel
)

__all__ = [
    # Clientes
    "OpenAIClient",
    
    # Configuración
    "get_settings",
    
    # Handlers
    "OpenAIHandler",
    "ValidationHandler",
    
    # Modelos específicos
    "EmbeddingBatchPayload",
    "EmbeddingBatchResult",
    
    # Modelos comunes
    "EmbeddingRequest",
    "EmbeddingResponse",
    "EmbeddingModel",
    
    # Servicios
    "EmbeddingService",
    
    # Workers
    "EmbeddingWorker",
]