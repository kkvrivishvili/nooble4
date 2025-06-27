"""
Rutas HTTP para interacciones de chat.

Simplificado ya que la mayoría de la comunicación es por WebSocket.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from ..services.orchestration_service import OrchestrationService
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
settings = get_settings()

# Instancia global del servicio
orchestration_service: Optional[OrchestrationService] = None


def get_orchestration_service() -> OrchestrationService:
    """Obtiene la instancia del servicio de orquestación."""
    if orchestration_service is None:
        raise RuntimeError("OrchestrationService no inicializado")
    return orchestration_service


class SessionStatusRequest(BaseModel):
    """Request para obtener estado de sesión."""
    session_id: str = Field(..., description="ID de la sesión")


class SessionStatusResponse(BaseModel):
    """Response con estado de sesión."""
    session_id: str
    status: str
    tenant_id: Optional[str] = None
    agent_id: Optional[str] = None
    connection_id: Optional[str] = None
    created_at: Optional[str] = None
    last_activity: Optional[str] = None
    message_count: Optional[int] = None
    current_task_id: Optional[str] = None


@router.post("/session/status", response_model=SessionStatusResponse)
async def get_session_status(
    request: SessionStatusRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
):
    """
    Obtiene el estado de una sesión de chat.
    
    Útil para reconectar o verificar el estado de una conversación.
    """
    try:
        # Crear action para obtener estado
        from common.models.actions import DomainAction
        
        action = DomainAction(
            action_type="orchestrator.session.status",
            tenant_id=uuid.UUID(x_tenant_id) if x_tenant_id else uuid.uuid4(),
            session_id=uuid.UUID(request.session_id),
            task_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),  # No relevante para esta consulta
            origin_service="api",
            data={"session_id": request.session_id}
        )
        
        result = await service.process_action(action)
        
        return SessionStatusResponse(**result)
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de sesión: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def chat_health():
    """Health check específico para chat."""
    return {
        "status": "healthy",
        "service": "chat",
        "timestamp": datetime.utcnow().isoformat()
    }


# Función para establecer el servicio
def set_orchestration_service(service: OrchestrationService):
    """Establece la instancia global del servicio."""
    global orchestration_service
    orchestration_service = service