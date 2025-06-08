"""
Rutas para gestión de conversaciones.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body, status
from pydantic import BaseModel, Field

from conversation_service.config.settings import get_settings
from conversation_service.models.conversation_model import (
    Conversation, Message, ConversationStatus
)
from conversation_service.services.conversation_service import ConversationService
from common.redis_pool import get_redis_client

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"]
)

# Modelos de request/response
class CreateConversationRequest(BaseModel):
    """Request para crear conversación."""
    session_id: str
    agent_id: str
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AddMessageRequest(BaseModel):
    """Request para agregar mensaje."""
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., description="Contenido del mensaje")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None

class UpdateConversationRequest(BaseModel):
    """Request para actualizar conversación."""
    status: Optional[str] = None
    customer_satisfaction: Optional[float] = None
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ConversationResponse(BaseModel):
    """Response con conversación."""
    success: bool = True
    conversation: Conversation

class MessageResponse(BaseModel):
    """Response con mensaje."""
    success: bool = True
    message: Message

class ConversationListResponse(BaseModel):
    """Response con lista de conversaciones."""
    success: bool = True
    conversations: List[Conversation]
    total: int
    page: int
    page_size: int

# Dependencias
async def get_conversation_service():
    """Dependency para obtener ConversationService."""
    redis_client = await get_redis_client()
    return ConversationService(redis_client)

# Rutas
@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Crea una nueva conversación."""
    try:
        conversation = await conversation_service.create_conversation(
            tenant_id=tenant_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
            user_id=request.user_id,
            metadata=request.metadata
        )
        
        return ConversationResponse(
            success=True,
            conversation=conversation
        )
        
    except Exception as e:
        logger.error(f"Error creando conversación: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando conversación: {str(e)}"
        )

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Obtiene una conversación por ID."""
    conversation = await conversation_service.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada"
        )
    
    # Verificar que pertenece al tenant
    if conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a esta conversación"
        )
    
    return ConversationResponse(
        success=True,
        conversation=conversation
    )

@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Actualiza una conversación."""
    # Verificar que existe y pertenece al tenant
    conversation = await conversation_service.get_conversation(conversation_id)
    if not conversation or conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada"
        )
    
    # Actualizar campos
    update_data = request.dict(exclude_unset=True)
    
    if "status" in update_data:
        success = await conversation_service.update_conversation_status(
            conversation_id,
            update_data["status"],
            update_data.get("metadata")
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error actualizando conversación"
            )
    
    # TODO: Actualizar otros campos como satisfaction, summary
    
    return {"success": True, "message": "Conversación actualizada"}

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Agrega un mensaje a la conversación."""
    # Verificar que existe y pertenece al tenant
    conversation = await conversation_service.get_conversation(conversation_id)
    if not conversation or conversation.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada"
        )
    
    try:
        message = await conversation_service.save_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata,
            tokens_used=request.tokens_used,
            processing_time_ms=request.processing_time_ms
        )
        
        return MessageResponse(
            success=True,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error agregando mensaje: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error agregando mensaje: {str(e)}"
        )

@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    user_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Lista conversaciones con filtros."""
    filters = {
        "user_id": user_id,
        "agent_id": agent_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to
    }
    
    # Eliminar None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    conversations = await conversation_service.search_conversations(
        tenant_id=tenant_id,
        filters=filters,
        page=page,
        page_size=page_size
    )
    
    return ConversationListResponse(
        success=True,
        conversations=conversations,
        total=len(conversations),  # TODO: Implementar count real
        page=page,
        page_size=page_size
    )

# Endpoint interno para Agent Execution Service
@router.get("/internal/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    tenant_id: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
    include_system: bool = Query(False),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    Endpoint interno para obtener historial de conversación.
    Usado por Agent Execution Service.
    """
    messages = await conversation_service.get_conversation_history(
        session_id=session_id,
        tenant_id=tenant_id,
        limit=limit,
        include_system=include_system
    )
    
    # Formatear mensajes
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "role": msg.role.value,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
            "metadata": msg.metadata
        })
    
    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "messages": formatted_messages,
            "total": len(formatted_messages)
        }
    }

# Endpoint interno para guardar mensajes
@router.post("/internal/save-message")
async def save_message_internal(
    request: Dict[str, Any] = Body(...),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """
    Endpoint interno para guardar mensajes.
    Usado por Agent Execution Service.
    """
    try:
        # Extraer datos del request
        session_id = request.get("session_id")
        tenant_id = request.get("tenant_id")
        role = request.get("role")
        content = request.get("content")
        message_type = request.get("message_type", "text")
        metadata = request.get("metadata", {})
        processing_time = request.get("processing_time")
        
        # Buscar conversación activa para la sesión
        conversation_key = f"session_conversation:{tenant_id}:{session_id}"
        redis_client = await get_redis_client()
        conversation_id = await redis_client.get(conversation_key) if redis_client else None
        
        # Si no hay conversación, crear una nueva
        if not conversation_id:
            agent_id = metadata.get("agent_id") or request.get("agent_id")
            if not agent_id:
                raise ValueError("agent_id requerido para crear conversación")
                
            conversation = await conversation_service.create_conversation(
                tenant_id=tenant_id,
                session_id=session_id,
                agent_id=agent_id,
                user_id=request.get("user_id")
            )
            conversation_id = conversation.id
        
        # Guardar mensaje
        message = await conversation_service.save_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
            processing_time_ms=int(processing_time * 1000) if processing_time else None
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "message_id": message.id
        }
        
    except Exception as e:
        logger.error(f"Error guardando mensaje interno: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

