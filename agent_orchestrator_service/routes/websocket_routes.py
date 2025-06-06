"""
Rutas WebSocket para comunicación en tiempo real.
"""

import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from starlette.websockets import WebSocketState

from services.websocket_manager import get_websocket_manager
from models.websocket_model import WebSocketMessage, WebSocketMessageType
from common.services.action_processor import ActionProcessor
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])
settings = get_settings()

# Obtener instancia singleton de WebSocketManager
websocket_manager = get_websocket_manager()

@router.websocket("/ws/{tenant_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str,
    session_id: str,
    user_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    Endpoint WebSocket para comunicación en tiempo real.
    
    Args:
        websocket: Conexión WebSocket
        tenant_id: ID del tenant
        session_id: ID de la sesión
        user_id: ID del usuario (opcional)
        token: Token de autenticación (opcional)
    """
    connection_id = None
    
    try:
        # Aceptar conexión
        await websocket.accept()
        
        # Validar token (implementación básica)
        if token and token != "valid_token":  # Implementar validación real
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Token inválido"}
            }))
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Extraer información del cliente
        client_info = {}
        if "user-agent" in websocket.headers:
            client_info["user_agent"] = websocket.headers["user-agent"]
        
        # Registrar conexión
        connection_id = await websocket_manager.connect(
            websocket=websocket,
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            user_agent=client_info.get("user_agent"),
            ip_address=websocket.client.host if hasattr(websocket, "client") else None
        )
        
        # Enviar confirmación de conexión
        ack_message = WebSocketMessage(
            type=WebSocketMessageType.CONNECTION_ACK,
            data={
                "connection_id": connection_id,
                "session_id": session_id,
                "message": "Conexión establecida"
            },
            session_id=session_id,
            tenant_id=tenant_id
        )
        
        await websocket_manager.send_message(connection_id, ack_message)
        
        # Bucle de recepción de mensajes
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break
                
            # Recibir mensaje con timeout
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Procesar mensaje del cliente
                await websocket_manager.handle_client_message(connection_id, message_data)
                
            except json.JSONDecodeError:
                logger.warning(f"Mensaje WebSocket inválido: {data}")
                await websocket_manager.send_error(connection_id, "Formato de mensaje inválido")
                
            except Exception as e:
                if "code = 1000" in str(e) or "code = 1001" in str(e):
                    # Desconexión normal
                    break
                logger.error(f"Error en bucle WebSocket: {str(e)}")
                await websocket_manager.send_error(connection_id, "Error interno")
                break
    
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectado: {tenant_id}/{session_id}")
    
    except Exception as e:
        logger.error(f"Error en WebSocket: {str(e)}")
        # Intentar cerrar conexión si aún está abierta
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1011)  # Internal error
        except:
            pass
    
    finally:
        # Limpiar conexión
        if connection_id:
            await websocket_manager.disconnect(connection_id)
            logger.info(f"Conexión limpiada: {connection_id}")

@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Obtiene estadísticas de conexiones WebSocket.
    
    Returns:
        Dict: Estadísticas de conexiones
    """
    return await websocket_manager.get_connection_stats()
