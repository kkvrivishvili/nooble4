"""Clientes para servicios externos.

Expone los clientes para comunicarse con otros servicios.
"""

from agent_management_service.clients.execution_client import ExecutionClient
from agent_management_service.clients.ingestion_client import IngestionClient

__all__ = ['ExecutionClient', 'IngestionClient']
