"""
Rutas API para interacciones de chat.

MODIFICADO: Uso de headers para resolver contexto y sistema de colas por tier.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from datetime import datetime

from common.services.domain_queue_manager import DomainQueueManager
from common.redis_pool import get_redis_client
from agent_orchestrator_service.handlers.context_handler import ContextHandler, get_context_handler
from agent_orchestrator_service.models.actions_model import ChatSendMessageAction, ChatProcessAction
from agent_orchestrator_service.config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
settings = get_settings()

# Modelos de API
class ChatMessageRequest(BaseModel):
    """Modelo para solicitud de mensaje de chat."""
    
    message: str = Field(..., description="Mensaje del usuario", min_length=1, max_length=4000)
    message_type: str = Field("text", description="Tipo de mensaje")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    max_iterations: Optional[int] = Field(None, description="Máximo de iteraciones")

class ChatResponse(BaseModel):
    """Modelo para respuesta de chat."""
    
    success: bool = Field(..., description="Si el request fue exitoso")
    task_id: str = Field(..., description="ID de la tarea")
    message: str = Field(..., description="Mensaje informativo")
    queue_name: Optional[str] = Field(None, description="Cola donde se encoló")
    estimated_time: Optional[int] = Field(None, description="Tiempo estimado en segundos")

# Dependencias
async def get_queue_manager() -> DomainQueueManager:
    """Obtiene instancia de DomainQueueManager."""
    redis_client = await get_redis_client()
    return DomainQueueManager(redis_client)

async def get_context_handler_dep() -> ContextHandler:
    """Dependencia para obtener ContextHandler."""
    redis_client = await get_redis_client()
    return await get_context_handler(redis_client, None)

# NUEVO: Validador de headers
async def validate_required_headers(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_agent_id: str = Header(..., alias="X-Agent-ID"),
    x_tenant_tier: str = Header(..., alias="X-Tenant-Tier"),
    x_session_id: str = Header(..., alias="X-Session-ID"),
    x_context_type: str = Header("agent", alias="X-Context-Type"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_conversation_id: Optional[str] = Header(None, alias="X-Conversation-ID"),
    x_collection_id: Optional[str] = Header(None, alias="X-Collection-ID"),
    x_request_source: Optional[str] = Header("web", alias="X-Request-Source"),
    x_client_version: Optional[str] = Header(None, alias="X-Client-Version")
) -> Dict[str, Any]:
    """
    Valida y extrae headers requeridos.
    
    Returns:
        Diccionario con todos los headers validados
    """
    return {
        "tenant_id": x_tenant_id,
        "agent_id": x_agent_id,
        "tenant_tier": x_tenant_tier,
        "session_id": x_session_id,
        "context_type": x_context_type,
        "user_id": x_user_id,
        "conversation_id": x_conversation_id,
        "collection_id": x_collection_id,
        "request_source": x_request_source,
        "client_version": x_client_version
    }

# Rutas
@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatMessageRequest,
    headers: Dict[str, Any] = Depends(validate_required_headers),
    context_handler: ContextHandler = Depends(get_context_handler_dep),
    queue_manager: DomainQueueManager = Depends(get_queue_manager)
):
    """
    Envía un mensaje de chat para procesamiento asíncrono.
    
    Headers requeridos:
    - X-Tenant-ID: ID del tenant
    - X-Agent-ID: ID del agente a usar
    - X-Tenant-Tier: Tier del tenant (free, advance, professional, enterprise)
    - X-Session-ID: ID de la sesión WebSocket
    
    Headers opcionales:
    - X-Context-Type: Tipo de contexto (default: agent)
    - X-User-ID: ID del usuario
    - X-Conversation-ID: ID de la conversación
    - X-Collection-ID: ID de collection específica
    - X-Request-Source: Origen del request (web, mobile, api)
    - X-Client-Version: Versión del cliente
    """
    try:
        logger.info(f"Chat request: tenant={headers['tenant_id']}, agent={headers['agent_id']}, tier={headers['tenant_tier']}")
        
        # 1. Crear contexto desde headers
        context = await context_handler.create_context_from_headers(
            tenant_id=headers["tenant_id"],
            agent_id=headers["agent_id"],
            tenant_tier=headers["tenant_tier"],
            context_type=headers["context_type"],
            session_id=headers["session_id"],
            user_id=headers["user_id"],
            conversation_id=headers["conversation_id"],
            collection_id=headers["collection_id"],
            # Metadatos adicionales
            request_source=headers["request_source"],
            client_version=headers["client_version"],
            original_message=request.message[:100]  # Primeros 100 chars para debug
        )
        
        # 2. Generar task_id único
        task_id = str(uuid4())
        
        # 3. Crear callback queue específico para este tenant
        callback_queue = f"{settings.callback_queue_prefix}:{headers['tenant_id']}:callbacks"
        
        # 4. Crear acción de procesamiento
        process_action = ChatProcessAction(
            task_id=task_id,
            tenant_id=headers["tenant_id"],
            tenant_tier=headers["tenant_tier"],
            session_id=headers["session_id"],
            execution_context=context.to_dict(),
            callback_queue=callback_queue,
            message=request.message,
            message_type=request.message_type,
            user_info=request.user_info,
            max_iterations=request.max_iterations,
            timeout=context.metadata.get("timeout", 120),
            metadata={
                "headers": headers,
                "created_at": context.created_at.isoformat()
            }
        )
        
        # 5. Encolar para procesamiento en Agent Execution Service
        queue_name = await queue_manager.enqueue_execution(
            action=process_action,
            target_domain="execution",
            context=context
        )
        
        # 6. Calcular tiempo estimado basado en tier
        tier_times = {
            "enterprise": 5,
            "professional": 10,
            "advance": 20,
            "free": 30
        }
        estimated_time = tier_times.get(headers["tenant_tier"], 30)
        
        # 7. Responder inmediatamente
        return ChatResponse(
            success=True,
            task_id=task_id,
            message=f"Mensaje enviado para procesamiento. Tier: {headers['tenant_tier']}",
            queue_name=queue_name,
            estimated_time=estimated_time
        )
        
    except HTTPException as e:
        # Re-lanzar HTTP exceptions (validaciones, permisos)
        raise e
    except Exception as e:
        logger.error(f"Error procesando mensaje: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )

@router.get("/stats")
async def get_chat_stats(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    queue_manager: DomainQueueManager = Depends(get_queue_manager)
):
    """
    Obtiene estadísticas de chat para un tenant.
    
    Headers requeridos:
    - X-Tenant-ID: ID del tenant
    """
    try:
        # Estadísticas de colas
        queue_stats = await queue_manager.get_queue_stats("execution")
        
        # TODO: Agregar estadísticas específicas del tenant
        return {
            "tenant_id": x_tenant_id,
            "queue_stats": queue_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )

@router.get("/health")
async def chat_health():
    """Health check específico para chat."""
    return {
        "status": "healthy",
        "service": "chat",
        "timestamp": datetime.utcnow().isoformat()
    }