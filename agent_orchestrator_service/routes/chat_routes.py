"""
Rutas HTTP para iniciar sesiones de chat.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
import uuid

from ..models.session_models import ChatInitRequest, ChatInitResponse
from ..services.orchestration_service import OrchestrationService
from ..dependencies import get_orchestration_service
from common.errors.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/start", response_model=ChatInitResponse)
async def start_chat_session(
    request: ChatInitRequest,
    http_request: Request,
    service: OrchestrationService = Depends(get_orchestration_service)
):
    """
    Inicia una nueva sesión de chat.
    
    - Extrae tenant_id y agent_id del JWT
    - Genera session_id y primer task_id
    - Pre-carga configuración del agente
    - Retorna info para conectar WebSocket
    """
    try:
        # Extraer info del JWT (asumiendo middleware que lo procesa)
        tenant_id = getattr(http_request.state, 'tenant_id', None)
        agent_id = getattr(http_request.state, 'agent_id', None)
        user_id = getattr(http_request.state, 'user_id', None)
        
        if not tenant_id or not agent_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id y agent_id son requeridos en el JWT"
            )
        
        # Generar IDs
        session_id = uuid.uuid4()
        task_id = uuid.uuid4()
        
        logger.info(
            f"Iniciando sesión de chat",
            extra={
                "session_id": str(session_id),
                "task_id": str(task_id),
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id)
            }
        )
        
        # Pre-cargar configuración del agente
        execution_config, query_config, rag_config = await service.get_agent_configurations(
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            session_id=str(session_id),
            task_id=str(task_id),
            user_id=str(user_id) if user_id else None
        )
        
        # Crear estado de sesión con configuración cacheada
        session_state = await service.create_session(
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            agent_config={
                "execution_config": execution_config.model_dump(),
                "query_config": query_config.model_dump(),
                "rag_config": rag_config.model_dump()
            }
        )
        
        # Construir URL de WebSocket
        ws_protocol = "wss" if http_request.url.scheme == "https" else "ws"
        ws_host = http_request.headers.get("host", "localhost")
        websocket_url = f"{ws_protocol}://{ws_host}/ws?session_id={session_id}"
        
        return ChatInitResponse(
            session_id=session_id,
            task_id=task_id,
            websocket_url=websocket_url,
            status="ready"
        )
        
    except ExternalServiceError as e:
        logger.error(f"Error obteniendo configuración: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error iniciando sesión: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: uuid.UUID,
    service: OrchestrationService = Depends(get_orchestration_service)
):
    """Obtiene el estado de una sesión."""
    session_state = await service.get_session_state(str(session_id))
    
    if not session_state:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    return {
        "session_id": session_state.session_id,
        "status": "active" if session_state.websocket_connected else "inactive",
        "created_at": session_state.created_at.isoformat(),
        "last_activity": session_state.last_activity.isoformat(),
        "total_tasks": session_state.total_tasks,
        "websocket_connected": session_state.websocket_connected
    }