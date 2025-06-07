"""
Gestión de WebSockets para comunicación en tiempo real.

Expone el administrador de conexiones y el despachador de eventos.
"""

from ingestion_service.websockets.connection_manager import ConnectionManager
from ingestion_service.websockets.event_dispatcher import EventDispatcher

__all__ = ['ConnectionManager', 'EventDispatcher']
