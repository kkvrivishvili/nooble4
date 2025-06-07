"""
Clientes para comunicación con servicios externos.

Expone los clientes utilizados para generar embeddings.
"""

from embedding_service.clients.openai_client import OpenAIClient

__all__ = ['OpenAIClient']
