"""
Workers para procesamiento asíncrono de acciones de embeddings.

Expone el worker para procesar acciones de dominio relacionadas con embeddings.
"""

from embedding_service.workers.embedding_worker import EmbeddingWorker

__all__ = ['EmbeddingWorker']
