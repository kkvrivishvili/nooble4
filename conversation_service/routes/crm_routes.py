"""
Rutas CRM para Frontend/Dashboard.
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query

from conversation_service.services.conversation_service import ConversationService
from common.redis_pool import get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/crm", tags=["crm"])

async def get_conversation_service():
    redis_client = await get_redis_client()
    return ConversationService(redis_client)

@router.get("/conversations/{tenant_id}")
async def list_conversations(
    tenant_id: str,
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Lista conversaciones para CRM."""
    conversations = await conversation_service.get_conversation_list(
        tenant_id=tenant_id,
        agent_id=agent_id,
        limit=limit
    )
    
    return {
        "success": True,
        "tenant_id": tenant_id,
        "conversations": conversations,
        "total": len(conversations)
    }

@router.get("/conversations/{tenant_id}/{conversation_id}")
async def get_conversation_detail(
    tenant_id: str,
    conversation_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Obtiene conversación completa."""
    result = await conversation_service.get_conversation_full(conversation_id, tenant_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return {
        "success": True,
        **result
    }

@router.get("/stats/{tenant_id}")
async def get_tenant_statistics(
    tenant_id: str,
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Obtiene estadísticas del tenant."""
    stats = await conversation_service.get_tenant_stats(tenant_id)
    
    return {
        "success": True,
        "stats": stats
    }
