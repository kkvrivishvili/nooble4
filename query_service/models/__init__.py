"""
Modelos de datos para Query Service.
"""

from .payloads import (
    QueryGeneratePayload,
    QuerySearchPayload,
    QueryStatusPayload,
    SearchResult,
    QueryGenerateResponse,
    QuerySearchResponse,
    QueryErrorResponse,
    EmbeddingRequest,
    CollectionConfig
)

__all__ = [
    'QueryGeneratePayload',
    'QuerySearchPayload',
    'QueryStatusPayload',
    'SearchResult',
    'QueryGenerateResponse',
    'QuerySearchResponse',
    'QueryErrorResponse',
    'EmbeddingRequest',
    'CollectionConfig'
]