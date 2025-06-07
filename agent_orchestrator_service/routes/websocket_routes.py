"""
Rutas WebSocket para comunicación en tiempo real.

MODIFICADO: Integración con sistema de colas por tier y validación de headers.
"""

import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from starlette.websockets import WebSocketState

from agent_orchestrator_service.services.websocket_manager import WebSocketManager
from agent_orchestrator_service.models.websocket_model import WebSocketMessage, WebSocketMessageType
from agent_orchestrator_service.handlers.context_handler import ContextHandler, get_context_handler
from agent_orchestrator_service.config.settings import get_settings
from common.redis_pool import get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])
settings = get_settings()

# Obtener instancia singleton de WebSocketManager
websocket_manager = WebSocketManager()

async def get_context_handler_dep() -> ContextHandler:
    """Dependencia para obtener ContextHandler."""
    redis_client = await get_redis_client()
    return await get_context_handler(redis_client, None)

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    tenant_id: str = Query(..., description="ID del tenant"),
    tenant_tier: str = Query(..., description="Tier del tenant"),
    agent_id: Optional[str] = Query(None, description="ID del agente (opcional)"),
    user_id: Optional[str] = Query(None, description="ID del usuario (opcional)"),
    token: Optional[str] = Query(None, description="Token de autenticación (opcional)")
):
    """
    Endpoint WebSocket para comunicación en tiempo real.
    
    MODIFICADO: Validación basada en query params que corresponden a headers.
    
    Args:
        websocket: Conexión WebSocket
        session_id: ID de la sesión
        tenant_id: ID del tenant (requerido)
        tenant_tier: Tier del tenant (requerido)
        agent_id: ID del agente (opcional)
        user_id: ID del usuario (opcional)
        token: Token de autenticación (opcional)
    """
    connection_id = f"{tenant_id}:{session_id}"
    
    try:
        # Validar parámetros requeridos
        if not tenant_id or not tenant_tier or not session_id:
            await websocket.close(code=1008, reason="Missing required parameters")
            return
        
        # Validar tier
        valid_tiers = {"free", "advance", "professional", "enterprise"}
        if tenant_tier not in valid_tiers:
            await websocket.close(code=1008, reason=f"Invalid tier: {tenant_tier}")
            return
        
        # TODO: Validar token de autenticación
        if token and not await _validate_websocket_token(token, tenant_id, session_id):
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Aceptar conexión
        await websocket.accept()
        logger.info(f"WebSocket conectado: session={session_id}, tenant={tenant_id}, tier={tenant_tier}")
        
        # Extraer información del cliente
        client_info = {}
        if "user-agent" in websocket.headers:
            client_info["user_agent"] = websocket.headers["user-agent"]
        
        # Registrar conexión
        connection_id = await websocket_manager.connect(
            websocket=websocket,
            session_id=session_id,
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,  # NUEVO: Registrar tier
            user_id=user_id,
            agent_id=agent_id,
            user_agent=client_info.get("user_agent"),
            ip_address=websocket.client.host if hasattr(websocket, "client") else None
        )
        
        # Enviar confirmación de conexión
        ack_message = WebSocketMessage(
            type=WebSocketMessageType.CONNECTION_ACK,
            data={
                "connection_id": connection_id,
                "session_id": session_id,
                "tenant_id": tenant_id,
                "tenant_tier": tenant_tier,
                "message": "Conexión establecida",
                "server_time": datetime.utcnow().isoformat()
            },
            session_id=session_id,
            tenant_id=tenant_id
        )
        
        await websocket_manager.send_message(connection_id, ack_message)
        
        # Bucle de recepción de mensajes
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break
                
            try:
                # Recibir mensaje con timeout
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Procesar mensaje del cliente
                await websocket_manager.handle_client_message(
                    connection_id, 
                    message_data,
                    tenant_id=tenant_id,
                    tenant_tier=tenant_tier
                )
                
            except json.JSONDecodeError:
                logger.warning(f"Mensaje WebSocket inválido: {data}")
                await websocket_manager.send_error(
                    connection_id, 
                    "Formato de mensaje inválido",
                    error_code="INVALID_JSON"
                )
                
            except Exception as e:
                if "code = 1000" in str(e) or "code = 1001" in str(e):
                    # Desconexión normal
                    break
                logger.error(f"Error en bucle WebSocket: {str(e)}")
                await websocket_manager.send_error(
                    connection_id, 
                    "Error interno",
                    error_code="INTERNAL_ERROR"
                )
                break
    
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectado: {tenant_id}/{session_id}")
    
    except Exception as e:
        logger.error(f"Error en WebSocket: {str(e)}")
        # Intentar cerrar conexión si aún está abierta
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1011, reason="Internal error")
        except:
            pass
    
    finally:
        # Limpiar conexión
        if connection_id:
            await websocket_manager.disconnect(connection_id, tenant_id, session_id)
            logger.info(f"Conexión WebSocket limpiada: {connection_id}")

@router.get("/ws/stats")
async def get_websocket_stats(
    tenant_id: Optional[str] = Query(None, description="Filtrar por tenant")
):
    """
    Obtiene estadísticas de conexiones WebSocket.
    
    Args:
        tenant_id: Filtrar estadísticas por tenant específico
        
    Returns:
        Estadísticas de conexiones
    """
    if tenant_id:
        return await websocket_manager.get_tenant_stats(tenant_id)
    else:
        return await websocket_manager.get_connection_stats()

@router.get("/ws/health")
async def websocket_health():
    """Health check específico para WebSockets."""
    stats = await websocket_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "service": "websocket",
        "active_connections": stats.get("total_connections", 0),
        "active_sessions": stats.get("total_sessions", 0),
        "timestamp": datetime.utcnow().isoformat()
    }

# Funciones auxiliares
async def _validate_websocket_token(token: str, tenant_id: str, session_id: str) -> bool:
    """
    Valida token de WebSocket.
    
    TODO: Implementar validación real de JWT/token.
    """
    # Validación básica temporal
    if token == "debug_token":
        return True
    
    # TODO: Implementar validación JWT real
    # jwt_payload = verify_jwt(token)
    # return jwt_payload.get("tenant_id") == tenant_id
    
    return True  # Temporal: permitir todas las conexiones