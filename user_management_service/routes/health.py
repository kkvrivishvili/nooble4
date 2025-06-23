"""
Rutas de health y métricas específicas.
"""

import logging
from fastapi import APIRouter, Depends

from agent_management_service.services.agent_service import AgentService
from common.redis_pool import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["health"]
)

async def get_agent_service():
    """Dependency para obtener AgentService."""
    redis_client = await get_redis_client()
    return AgentService(redis_client)

@router.get("/metrics")
async def get_metrics(
    agent_service: AgentService = Depends(get_agent_service)
):
    """Métricas específicas del servicio."""
    try:
        # TODO: Implementar métricas reales
        return {
            "service": "agent-management",
            "agents_in_cache": 0,  # Placeholder
            "templates_loaded": 3,
            "cache_hits": 0,
            "cache_misses": 0
        }
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {str(e)}")
        return {"error": "Error obteniendo métricas"}

