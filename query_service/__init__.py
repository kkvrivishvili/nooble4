"""
Query Service - Servicio de búsqueda vectorial y generación RAG.

Este servicio maneja consultas de búsqueda vectorial y generación
de respuestas usando Retrieval-Augmented Generation (RAG).
"""

__version__ = "1.0.0"

from .clients import GroqClient, VectorClient, EmbeddingClient
from .config import QueryServiceSettings, get_settings
from .handlers import SimpleHandler, AdvanceHandler, RAGHandler
from .models import (
    ACTION_QUERY_SIMPLE,
    ACTION_QUERY_ADVANCE,
    ACTION_QUERY_RAG,
    QueryAdvancePayload,
    QueryAdvanceResponseData,
    QueryRAGPayload,
    QueryRAGResponseData,
)
from .services import QueryService
from .workers import QueryWorker

__all__ = [
    "GroqClient",
    "VectorClient",
    "EmbeddingClient",
    "QueryServiceSettings",
    "get_settings",
    "SimpleHandler",
    "AdvanceHandler",
    "RAGHandler",
    "ACTION_QUERY_SIMPLE",
    "ACTION_QUERY_ADVANCE",
    "ACTION_QUERY_RAG",
    "QueryAdvancePayload",
    "QueryAdvanceResponseData",
    "QueryRAGPayload",
    "QueryRAGResponseData",
    "QueryService",
    "QueryWorker",
]