"""
Rutas para analytics de conversaciones.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field

from conversation_service.config.settings import get_settings
from conversation_service.services.conversation_service import ConversationService
from common.redis_pool import get_redis_client

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"]
)

# Modelos de response
class ConversationSummaryResponse(BaseModel):
    """Response con resumen de conversaciones."""
    success: bool = True
    period: str
    metrics: Dict[str, Any]

class AgentPerformanceResponse(BaseModel):
    """Response con performance de agente."""
    success: bool = True
    agent_id: str
    metrics: Dict[str, Any]

# Dependencias
async def get_conversation_service():
    """Dependency para obtener ConversationService."""
    redis_client = await get_redis_client()
    return ConversationService(redis_client)

# Rutas
@router.get("/conversations/summary", response_model=ConversationSummaryResponse)
async def get_conversations_summary(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    period: str = Query("last_30_days", description="Período de análisis"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Obtiene resumen de analytics de conversaciones."""
    # TODO: Implementar analytics reales
    # Por ahora retorna datos mock
    
    metrics = {
        "total_conversations": 150,
        "active_conversations": 12,
        "avg_satisfaction": 4.2,
        "resolution_rate": 0.85,
        "avg_response_time_seconds": 3.5,
        "total_messages": 1250,
        "top_topics": [
            {"topic": "billing", "count": 45},
            {"topic": "support", "count": 38},
            {"topic": "product", "count": 27}
        ]
    }
    
    return ConversationSummaryResponse(
        success=True,
        period=period,
        metrics=metrics
    )

@router.get("/agents/{agent_id}/performance", response_model=AgentPerformanceResponse)
async def get_agent_performance(
    agent_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    period: str = Query("last_7_days", description="Período de análisis"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Obtiene métricas de performance de un agente."""
    # TODO: Implementar analytics reales
    # Por ahora retorna datos mock
    
    metrics = {
        "total_conversations": 45,
        "avg_satisfaction": 4.5,
        "resolution_rate": 0.9,
        "avg_response_time_seconds": 2.8,
        "total_messages": 380,
        "sentiment_distribution": {
            "positive": 0.7,
            "neutral": 0.2,
            "negative": 0.1
        },
        "busiest_hours": [
            {"hour": 10, "conversations": 8},
            {"hour": 14, "conversations": 12},
            {"hour": 16, "conversations": 10}
        ]
    }
    
    return AgentPerformanceResponse(
        success=True,
        agent_id=agent_id,
        metrics=metrics
    )

@router.post("/conversations/{conversation_id}/analyze")
async def analyze_conversation(
    conversation_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    analysis_types: List[str] = Query(..., description="Tipos de análisis"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Solicita análisis de una conversación específica."""
    # Verificar que la conversación existe y pertenece al tenant
    conversation = await conversation_service.get_conversation(conversation_id)
    if not conversation or conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=404,
            detail="Conversación no encontrada"
        )
    
    # TODO: Encolar tarea de análisis asíncrono
    # Por ahora retorna confirmación
    
    return {
        "success": True,
        "message": "Análisis encolado",
        "conversation_id": conversation_id,
        "analysis_types": analysis_types,
        "estimated_time_seconds": 30
    }
