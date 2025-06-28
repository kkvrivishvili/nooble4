"""
Rutas WebSocket para comunicación en tiempo real.
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from datetime import datetime
import uuid

from ..dependencies import get_orchestration_service, get_ws_manager
from ..models.websocket_model import WebSocketMessage, WebSocketMessageType
from ..models.session_models import ChatMessageRequest
from common.models.actions import DomainAction
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Query(..., description="ID de la sesión desde /start")
):
    """
    Endpoint WebSocket para chat en tiempo real.
    
    Requiere session_id obtenido desde POST /api/chat/start
    """
    service = get_orchestration_service()
    connection_id = str(uuid.uuid4())
    
    try:
        # Validar y recuperar sesión
        session_state = await service.get_session_state(session_id)
        if not session_state:
            await websocket.close(code=1008, reason="Sesión no encontrada")
            return
        
        # Aceptar conexión
        await websocket.accept()
        
        # Registrar conexión WebSocket
        await service.register_websocket_connection(
            session_id=session_id,
            websocket=websocket,
            connection_id=connection_id
        )
        
        # Enviar ACK de conexión
        await websocket.send_json(
            WebSocketMessage(
                type=WebSocketMessageType.CONNECTION_ACK,
                data={
                    "session_id": str(session_state.session_id),
                    "connection_id": connection_id,
                    "message": "Conexión establecida"
                }
            ).model_dump()
        )
        
        # Loop principal de mensajes
        while True:
            # Recibir mensaje
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                chat_request = ChatMessageRequest(**message_data)
            except (json.JSONDecodeError, ValueError) as e:
                await websocket.send_json(
                    WebSocketMessage(
                        type=WebSocketMessageType.ERROR,
                        data={
                            "error": "Formato de mensaje inválido",
                            "details": str(e)
                        }
                    ).model_dump()
                )
                continue
            
            # Generar nuevo task_id para este mensaje
            task_id = uuid.uuid4()
            
            # Notificar que se creó la tarea
            await websocket.send_json(
                WebSocketMessage(
                    type=WebSocketMessageType.TASK_CREATED,
                    task_id=task_id,
                    data={
                        "message": "Procesando mensaje...",
                        "task_id": str(task_id)
                    }
                ).model_dump()
            )
            
            try:
                # Procesar mensaje
                response = await service.process_chat_message(
                    session_id=session_id,
                    task_id=task_id,
                    message=chat_request.message,
                    message_type=chat_request.type,
                    metadata=chat_request.metadata
                )
                
                # Enviar respuesta
                await websocket.send_json(
                    WebSocketMessage(
                        type=WebSocketMessageType.RESPONSE,
                        task_id=task_id,
                        data=response
                    ).model_dump()
                )
                
                # Notificar completado
                await websocket.send_json(
                    WebSocketMessage(
                        type=WebSocketMessageType.TASK_COMPLETED,
                        task_id=task_id,
                        data={"status": "completed"}
                    ).model_dump()
                )
                
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}", exc_info=True)
                await websocket.send_json(
                    WebSocketMessage(
                        type=WebSocketMessageType.ERROR,
                        task_id=task_id,
                        data={
                            "error": "Error procesando mensaje",
                            "details": str(e)
                        }
                    ).model_dump()
                )
    
    except WebSocketDisconnect:
        logger.info(f"Cliente desconectado: session_id={session_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Error interno")
        except:
            pass
    finally:
        # Limpiar conexión
        await service.unregister_websocket_connection(session_id, connection_id)