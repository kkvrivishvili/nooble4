"""
Rutas de health check para Agent Orchestrator Service.
"""

import logging
from fastapi import APIRouter, Depends

from common.helpers.health import get_health_status, HealthStatus
from services.websocket_manager import get_websocket_manager
from config.settings import get_settings, OrchestratorSettings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
settings = get_settings()

# Obtener instancia singleton de WebSocketManager
websocket_manager = get_websocket_manager()

@router.get("/health")
async def health_check():
    """
    Endpoint de health check básico.
    
    Returns:
        Dict: Estado de salud del servicio
    """
    return {"status": "ok", "service": "agent_orchestrator"}

@router.get("/health/detailed", response_model=HealthStatus)
async def detailed_health():
    """
    Health check detallado con verificación de dependencias.
    
    Returns:
        HealthStatus: Estado detallado del servicio y sus dependencias
    """
    # Obtener estado base
    health_status = await get_health_status(
        service_name="agent_orchestrator",
        settings=settings
    )
    
    # Agregar información específica del servicio
    try:
        # Estadísticas de WebSocket
        ws_stats = await websocket_manager.get_connection_stats()
        health_status.details["websocket"] = {
            "status": "ok",
            "connections": ws_stats["total_connections"],
            "sessions": ws_stats["total_sessions"],
            "tenants": ws_stats["total_tenants"]
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas WebSocket: {str(e)}")
        health_status.details["websocket"] = {
            "status": "error",
            "error": str(e)
        }
        health_status.healthy = False
    
    return health_status
