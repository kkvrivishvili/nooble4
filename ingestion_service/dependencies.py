"""Dependency injection for FastAPI"""
from typing import Optional
from functools import lru_cache

from .services import IngestionService
from .websocket import WebSocketManager

_ingestion_service: Optional[IngestionService] = None
_ws_manager: Optional[WebSocketManager] = None


def set_ingestion_service(service: IngestionService):
    """Set the global ingestion service instance"""
    global _ingestion_service
    _ingestion_service = service


def set_ws_manager(manager: WebSocketManager):
    """Set the global WebSocket manager instance"""
    global _ws_manager
    _ws_manager = manager


def get_ingestion_service() -> IngestionService:
    """Get the ingestion service instance"""
    if _ingestion_service is None:
        raise RuntimeError("IngestionService not initialized")
    return _ingestion_service


def get_ws_manager() -> WebSocketManager:
    """Get the WebSocket manager instance"""
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _ws_manager
