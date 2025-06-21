"""
Modelos de datos para Embedding Service.
"""

# Importar modelos específicos del servicio (batch processing)
from .payloads import (
    EmbeddingBatchPayload,
    EmbeddingBatchResult
)

# Importar modelos comunes desde common
from common.models.chat_models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingModel,
    TokenUsage
)

__all__ = [
    # Modelos específicos del servicio
    'EmbeddingBatchPayload',
    'EmbeddingBatchResult',
    
    # Modelos de common
    'EmbeddingRequest',
    'EmbeddingResponse',
    'EmbeddingModel',
    'TokenUsage'
]