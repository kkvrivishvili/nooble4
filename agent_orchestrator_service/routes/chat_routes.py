"""
Rutas API para interacciones de chat.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field

from common.services.action_processor import ActionProcessor
from models.actions_model import ChatProcessAction, ChatStatusAction, ChatCancelAction
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
settings = get_settings()

# Modelos de API
class ChatMessageRequest(BaseModel):
    """Modelo para solicitud de mensaje de chat."""
    
    agent_id: UUID = Field(..., description="ID del agente a usar")
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    session_id: str = Field(..., description="ID de la sesión")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    timeout: Optional[int] = Field(None, description="Timeout personalizado")
    max_iterations: Optional[int] = Field(None, description="Máximo de iteraciones")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversación")

class ChatResponse(BaseModel):
    """Modelo para respuesta de chat."""
    
    task_id: str = Field(..., description="ID de la tarea")
    status: str = Field(..., description="Estado de la tarea")
    message: str = Field(..., description="Mensaje informativo")

class StatusRequest(BaseModel):
    """Modelo para solicitud de estado."""
    
    task_id: str = Field(..., description="ID de la tarea")

class StatusResponse(BaseModel):
    """Modelo para respuesta de estado."""
    
    task_id: str = Field(..., description="ID de la tarea")
    status: str = Field(..., description="Estado de la tarea")
    updated_at: float = Field(..., description="Timestamp de actualización")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")

# Dependencias
async def get_action_processor() -> ActionProcessor:
    """Obtiene instancia de ActionProcessor."""
    return ActionProcessor()

def get_tenant_id(
    x_tenant_id: str = Header(..., description="ID del tenant")
) -> str:
    """Extrae tenant ID del header."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header es requerido")
    return x_tenant_id

# Rutas
@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatMessageRequest,
    tenant_id: str = Depends(get_tenant_id),
    action_processor: ActionProcessor = Depends(get_action_processor)
):
    """
    Envía un mensaje de chat para procesamiento asíncrono.
    
    Args:
        request: Datos del mensaje
        tenant_id: ID del tenant (del header)
        action_processor: Procesador de acciones de dominio
        
    Returns:
        ChatResponse: Respuesta con ID de tarea
    """
    try:
        # Crear Domain Action
        action = ChatProcessAction(
            tenant_id=tenant_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            message=request.message,
            message_type=request.message_type,
            user_info=request.user_info,
            context=request.context,
            timeout=request.timeout,
            conversation_id=request.conversation_id,
            callback_queue=f"orchestrator:callback:{tenant_id}"
        )
        
        # Procesar la acción
        task_id = await action_processor.process_action(action)
        
        if not task_id:
            raise HTTPException(status_code=500, detail="Error procesando mensaje")
        
        return ChatResponse(
            task_id=task_id,
            status="processing",
            message="Mensaje enviado para procesamiento"
        )
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/status", response_model=StatusResponse)
async def get_status(
    request: StatusRequest,
    tenant_id: str = Depends(get_tenant_id),
    action_processor: ActionProcessor = Depends(get_action_processor)
):
    """
    Obtiene el estado de una tarea.
    
    Args:
        request: Datos de la solicitud
        tenant_id: ID del tenant (del header)
        action_processor: Procesador de acciones de dominio
        
    Returns:
        StatusResponse: Estado de la tarea
    """
    try:
        # Crear Domain Action
        action = ChatStatusAction(
            tenant_id=tenant_id,
            task_id=request.task_id
        )
        
        # Procesar la acción
        result = await action_processor.process_action(action)
        
        if not result or not isinstance(result, dict):
            raise HTTPException(status_code=404, detail=f"Tarea {request.task_id} no encontrada")
        
        return StatusResponse(
            task_id=request.task_id,
            status=result.get("status", "unknown"),
            updated_at=result.get("updated_at", 0),
            metadata=result.get("metadata", {})
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error obteniendo estado de tarea: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cancel", response_model=ChatResponse)
async def cancel_task(
    request: StatusRequest,
    tenant_id: str = Depends(get_tenant_id),
    action_processor: ActionProcessor = Depends(get_action_processor)
):
    """
    Cancela una tarea en progreso.
    
    Args:
        request: Datos de la solicitud
        tenant_id: ID del tenant (del header)
        action_processor: Procesador de acciones de dominio
        
    Returns:
        ChatResponse: Confirmación de cancelación
    """
    try:
        # Crear Domain Action
        action = ChatCancelAction(
            tenant_id=tenant_id,
            task_id=request.task_id
        )
        
        # Procesar la acción
        result = await action_processor.process_action(action)
        
        if not result:
            raise HTTPException(status_code=500, detail="Error procesando cancelación")
        
        return ChatResponse(
            task_id=request.task_id,
            status="cancelling",
            message="Solicitud de cancelación en progreso"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error cancelando tarea: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
