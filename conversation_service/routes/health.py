"""
Rutas de health check específicas del servicio.
"""

import logging
from fastapi import APIRouter, Depends

from conversation_service.services.conversation_service import ConversationService
from common.redis_pool import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["health"]
)

async def get_conversation_service():
    """Dependency para obtener ConversationService."""
    redis_client = await get_redis_client()
    return ConversationService(redis_client)

@router.get("/metrics")
async def get_metrics(
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Métricas específicas del servicio."""
    try:
        # TODO: Implementar métricas reales
        return {
            "service": "conversation",
            "conversations_cached": 0,  # Placeholder
            "messages_cached": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_conversation_length": 0
        }
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {str(e)}")
        return {"error": "Error obteniendo métricas"}

@router.get("/status")
async def get_service_status():
    """Estado detallado del servicio."""
    return {
        "service": "conversation",
        "status": "operational",
        "features": {
            "crud": "enabled",
            "analytics": "partial",
            "crm_integration": "disabled",
            "search": "disabled"
        },
        "dependencies": {
            "redis": "connected",
            "database": "not_configured"
        }
    }