"""Dependency injection for FastAPI"""
from typing import Optional

from .services import OrchestrationService
from .websocket import WebSocketManager

_orchestration_service: Optional[OrchestrationService] = None
_ws_manager: Optional[WebSocketManager] = None


def set_orchestration_service(service: OrchestrationService):
    """Set the global orchestration service instance"""
    global _orchestration_service
    _orchestration_service = service


def set_ws_manager(manager: WebSocketManager):
    """Set the global WebSocket manager instance"""
    global _ws_manager
    _ws_manager = manager


def get_orchestration_service() -> OrchestrationService:
    """Get the orchestration service instance"""
    if _orchestration_service is None:
        raise RuntimeError("OrchestrationService not initialized")
    return _orchestration_service


def get_ws_manager() -> WebSocketManager:
    """Get the WebSocket manager instance"""
    if _ws_manager is None:
        raise RuntimeError("WebSocketManager not initialized")
    return _ws_manager