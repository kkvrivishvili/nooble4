"""
Rutas WebSocket para comunicación en tiempo real.
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from datetime import datetime

from ..dependencies import get_orchestration_service, get_ws_manager
from ..models.websocket_model import WebSocketMessage, WebSocketMessageType
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])
settings = get_settings()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(..., description="ID de la sesión"),
    tenant_id: str = Query(..., description="ID del tenant"),
    agent_id: str = Query(..., description="ID del agente"),
    user_id: Optional[str] = Query(None, description="ID del usuario"),
    token: Optional[str] = Query(None, description="Token de autenticación")
):
    """Endpoint WebSocket para chat en tiempo real."""
    service = get_orchestration_service()
    websocket_manager = get_ws_manager()
    
    try:
        # Validar parámetros requeridos
        if not all([session_id, tenant_id, agent_id]):
            await websocket.close(code=1008, reason="Parámetros requeridos faltantes")
            return
        
        # TODO: Validar token de autenticación
        if token and not await _validate_token(token, tenant_id, user_id):
            await websocket.close(code=1008, reason="Token inválido")
            return
        
        # Conectar
        connection_id = await websocket_manager.connect(
            websocket=websocket,
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            metadata={
                "connected_from": "websocket_endpoint",
                "user_agent": websocket.headers.get("user-agent", "unknown")
            }
        )
        
        logger.info(
            f"Nueva conexión WebSocket: {connection_id} "
            f"(session: {session_id}, tenant: {tenant_id}, agent: {agent_id})"
        )
        
        # Loop principal
        while True:
            # Recibir mensaje
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    WebSocketMessage(
                        type=WebSocketMessageType.ERROR,
                        data={
                            "error": "Formato de mensaje inválido",
                            "error_type": "invalid_json"
                        }
                    )
                )
                continue
            
            # Procesar mensaje
            processed_data = await websocket_manager.handle_client_message(
                websocket,
                session_id,
                message_data
            )
            
            # Si es un mensaje de chat (no de control), procesarlo
            if processed_data:
                await service.process_websocket_message(session_id, processed_data)
    
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectado: session_id={session_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Error interno del servidor")
        except:
            pass
    finally:
        # Limpiar conexión
        await websocket_manager.disconnect(websocket, session_id)
        logger.info(f"Conexión limpiada: session_id={session_id}")


@router.get("/ws/stats")
async def get_websocket_stats(
    websocket_manager = Depends(get_ws_manager)
):
    """Obtiene estadísticas de conexiones WebSocket."""
    return websocket_manager.get_stats()


async def _validate_token(token: str, tenant_id: str, user_id: Optional[str]) -> bool:
    """Valida el token de autenticación."""
    # Validación temporal para desarrollo
    if token == "dev_token":
        return True
    
    # TODO: Implementar validación JWT real
    return True