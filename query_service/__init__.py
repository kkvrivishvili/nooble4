"""
Query Service - Servicio de búsqueda vectorial y generación RAG.

Este servicio maneja consultas de búsqueda vectorial y generación
de respuestas usando Retrieval-Augmented Generation (RAG).
"""

__version__ = "1.0.0"

from .clients import GroqClient, VectorClient, EmbeddingClient
from .config import QueryServiceSettings, get_settings
from .handlers import SimpleHandler, AdvanceHandler, RAGHandler

__all__ = [
    "GroqClient",
    "VectorClient",
    "EmbeddingClient",
    "QueryServiceSettings",
    "get_settings",
    "SimpleHandler",
    "AdvanceHandler",
    "RAGHandler",
]