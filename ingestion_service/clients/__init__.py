"""
Clientes para comunicación con servicios externos.

Expone los clientes utilizados para comunicarse con otros servicios.
"""

from ingestion_service.clients.embedding_client import EmbeddingClient

__all__ = ['EmbeddingClient']
