"""
Endpoints WebSocket para actualizaciones en tiempo real.

Este módulo implementa las rutas para:
- Conectarse a WebSocket para recibir eventos de tareas
- Manejar autenticación y validación de conexiones
"""

import logging
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from fastapi.responses import JSONResponse

from common.context import with_context, Context, create_context
from common.errors import AuthenticationError, ValidationError
from ingestion_service.config.settings import get_settings
from ingestion_service.models.events import WebSocketEvent, TaskStatusEvent, EventType
from ingestion_service.models.tasks import TaskStatus
from ingestion_service.websockets.connection_manager import connection_manager
from ingestion_service.services.queue import queue_service

settings = get_settings()
logger = logging.getLogger(__name__)

# Crear router para las rutas WebSocket
router = APIRouter(
    tags=["websockets"],
)


async def verify_task_access(
    task_id: str, 
    tenant_id: str,
    token: str
) -> bool:
    """Verifica que el cliente tiene acceso a la tarea especificada.
    
    Args:
        task_id: ID de la tarea
        tenant_id: ID del tenant
        token: Token de autenticación
        
    Returns:
        bool: True si el acceso es permitido
        
    Raises:
        AuthenticationError: Si falla la autenticación
        ValidationError: Si la tarea no existe o no pertenece al tenant
    """
    # TODO: Implementar verificación de token JWT
    # Por ahora simplemente verificamos que la tarea exista para el tenant
    
    # Verificar si la tarea existe en Redis
    task_info = await queue_service.get_task_status(task_id)
    
    if not task_info:
        raise ValidationError(f"Tarea no encontrada: {task_id}")
    
    # TODO: En una implementación real, verificaríamos el tenant_id
    # contra la tarea almacenada en base de datos
    
    return True


@router.websocket("/ws/tasks/{task_id}")
@with_context
async def websocket_task_endpoint(
    websocket: WebSocket,
    task_id: str,
    tenant_id: str = Query(...),
    token: str = Query(...),
    ctx: Optional[Context] = None
):
    """Endpoint WebSocket para recibir actualizaciones en tiempo real de una tarea.
    
    Args:
        websocket: Conexión WebSocket
        task_id: ID de la tarea
        tenant_id: ID del tenant
        token: Token de autenticación
        ctx: Contexto de la operación
    """
    connection_id = f"{tenant_id}:{task_id}"
    
    try:
        # Verificar acceso
        try:
            has_access = await verify_task_access(task_id, tenant_id, token)
            if not has_access:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except (AuthenticationError, ValidationError) as e:
            logger.warning(f"Acceso denegado al WebSocket para tarea {task_id}: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Aceptar conexión
        await connection_manager.connect(
            websocket=websocket,
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        # Enviar evento inicial con estado actual
        task_status = await queue_service.get_task_status(task_id)
        
        if task_status:
            current_status = TaskStatus(task_status.get("status", "pending"))
            
            welcome_event = TaskStatusEvent(
                task_id=task_id,
                tenant_id=tenant_id,
                event_type=EventType.TASK_STATUS,
                current_status=current_status,
                message=f"Conectado a la tarea {task_id}"
            )
            
            await connection_manager.send_personal_message(
                message=welcome_event,
                websocket=websocket
            )
        
        # Mantener la conexión abierta y escuchar mensajes
        # (principalmente para detectar desconexiones)
        try:
            while True:
                data = await websocket.receive_text()
                # Por ahora ignoramos los mensajes entrantes
                # Se podría implementar comandos como "ping" o "refresh"
        except WebSocketDisconnect:
            # Desconectar cuando el cliente cierra la conexión
            await connection_manager.disconnect(websocket, task_id, tenant_id)
        
    except Exception as e:
        logger.error(f"Error en conexión WebSocket para tarea {task_id}: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
