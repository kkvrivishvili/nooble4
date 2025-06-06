"""
Handlers para Domain Actions en Agent Orchestrator Service.

Implementa los handlers para procesar los diferentes tipos
de Domain Actions en el servicio de orquestación.
"""

import logging
from typing import Dict, Any, Optional
import json
import asyncio
from uuid import uuid4

from agent_orchestrator_service.models.actions import (
    WebSocketSendAction, WebSocketBroadcastAction,
    ChatProcessAction, ChatStatusAction, ChatCancelAction
)

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handler para acciones relacionadas con WebSockets."""
    
    def __init__(self, connection_manager):
        """
        Inicializa handler con dependencias.
        
        Args:
            connection_manager: Gestor de conexiones WebSocket
        """
        self.connection_manager = connection_manager
    
    async def handle_send(self, action: WebSocketSendAction) -> Dict[str, Any]:
        """
        Envía mensaje a una sesión específica.
        
        Args:
            action: Acción con datos del mensaje
            
        Returns:
            Resultado del envío
        """
        try:
            session_id = action.session_id
            
            if not session_id:
                return {
                    "success": False,
                    "error": {
                        "type": "InvalidAction",
                        "message": "Se requiere session_id para enviar mensaje"
                    }
                }
            
            # Preparar mensaje para WebSocket
            message = {
                "type": action.message_type,
                "data": action.message_data
            }
            
            # Intentar enviar mensaje
            sent = await self.connection_manager.send_message_to_session(
                session_id=session_id,
                message=message
            )
            
            if sent:
                logger.info(f"Mensaje enviado a sesión {session_id}")
                return {"success": True, "sent": True}
            else:
                logger.warning(f"No se encontró sesión activa {session_id}")
                return {
                    "success": True,  # La acción se procesó correctamente
                    "sent": False,    # Pero no se pudo enviar el mensaje
                    "reason": "session_not_found"
                }
                
        except Exception as e:
            logger.error(f"Error enviando mensaje WebSocket: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_broadcast(self, action: WebSocketBroadcastAction) -> Dict[str, Any]:
        """
        Realiza broadcast a todas las conexiones de un tenant.
        
        Args:
            action: Acción con datos del broadcast
            
        Returns:
            Resultado del broadcast
        """
        try:
            tenant_id = action.tenant_id
            
            # Preparar mensaje
            message = {
                "type": action.message_type,
                "data": action.message_data
            }
            
            # Enviar broadcast
            if action.target_sessions:
                # Broadcast a sesiones específicas
                count = await self.connection_manager.send_to_sessions(
                    sessions=action.target_sessions,
                    message=message
                )
            else:
                # Broadcast a todo el tenant
                count = await self.connection_manager.broadcast_to_tenant(
                    tenant_id=tenant_id,
                    message=message
                )
            
            logger.info(f"Broadcast enviado a {count} conexiones del tenant {tenant_id}")
            return {"success": True, "connections_reached": count}
            
        except Exception as e:
            logger.error(f"Error en broadcast WebSocket: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }


class ChatHandler:
    """Handler para acciones de procesamiento de chat."""
    
    def __init__(self, chat_service):
        """
        Inicializa handler con servicios.
        
        Args:
            chat_service: Servicio para gestión de chats
        """
        self.chat_service = chat_service
    
    async def handle_process(self, action: ChatProcessAction) -> Dict[str, Any]:
        """
        Procesa un mensaje de chat enviándolo al agente.
        
        Args:
            action: Acción con datos del mensaje
            
        Returns:
            Resultado preliminar del procesamiento
        """
        try:
            # Validar datos mínimos
            if not action.agent_id or not action.message:
                return {
                    "success": False,
                    "error": {
                        "type": "InvalidAction",
                        "message": "Se requieren agent_id y message"
                    }
                }
            
            # Generar task_id si no existe
            task_id = action.task_id or str(uuid4())
            
            # Enviar mensaje al servicio de ejecución
            await self.chat_service.send_message(
                agent_id=action.agent_id,
                message=action.message,
                session_id=action.session_id,
                conversation_id=action.conversation_id,
                task_id=task_id,
                message_type=action.message_type,
                user_info=action.user_info,
                context=action.context,
                timeout=action.timeout,
                callback_queue=action.callback_queue
            )
            
            # Devolver confirmación inicial
            return {
                "success": True,
                "task_id": task_id,
                "status": "processing"
            }
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de chat: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_status(self, action: ChatStatusAction) -> Dict[str, Any]:
        """
        Consulta el estado de una tarea.
        
        Args:
            action: Acción con ID de tarea
            
        Returns:
            Estado de la tarea
        """
        try:
            # Validar task_id
            if not action.task_id:
                return {
                    "success": False,
                    "error": {
                        "type": "InvalidAction",
                        "message": "Se requiere task_id"
                    }
                }
            
            # Obtener estado
            status = await self.chat_service.get_task_status(action.task_id)
            
            return {
                "success": True,
                "task_id": action.task_id,
                "status": status.dict() if status else {"status": "unknown"}
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estado de tarea: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_cancel(self, action: ChatCancelAction) -> Dict[str, Any]:
        """
        Cancela una tarea en ejecución.
        
        Args:
            action: Acción con ID de tarea
            
        Returns:
            Resultado de la cancelación
        """
        try:
            # Validar task_id
            if not action.task_id:
                return {
                    "success": False,
                    "error": {
                        "type": "InvalidAction",
                        "message": "Se requiere task_id"
                    }
                }
            
            # Cancelar tarea
            cancelled = await self.chat_service.cancel_task(
                task_id=action.task_id,
                reason=action.reason or "Cancelado por usuario"
            )
            
            return {
                "success": True,
                "task_id": action.task_id,
                "cancelled": cancelled
            }
            
        except Exception as e:
            logger.error(f"Error cancelando tarea: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
