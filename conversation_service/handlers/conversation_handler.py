"""
Handler para Domain Actions de conversaciones.
"""

import logging
from typing import Dict, Any
import time

from common.models.actions import DomainAction
from conversation_service.models.actions_model import (
    ConversationSaveAction,
    ConversationRetrieveAction
)
from conversation_service.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

class ConversationHandler:
    """Handler para acciones de conversación."""
    
    def __init__(self, conversation_service: ConversationService):
        """Inicializa handler."""
        self.conversation_service = conversation_service
    
    async def handle_save_message(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja guardado de mensajes."""
        start_time = time.time()
        
        try:
            # Convertir a tipo específico
            save_action = ConversationSaveAction.parse_obj(action.dict())
            
            # Si no hay conversation_id, crear nueva conversación
            if not save_action.conversation_id:
                conversation = await self.conversation_service.create_conversation(
                    tenant_id=save_action.tenant_id,
                    session_id=save_action.session_id,
                    agent_id=save_action.agent_id,
                    user_id=save_action.user_id
                )
                conversation_id = conversation.id
            else:
                conversation_id = save_action.conversation_id
            
            # Guardar mensaje
            message = await self.conversation_service.save_message(
                conversation_id=conversation_id,
                role=save_action.role,
                content=save_action.content,
                agent_id=save_action.agent_id,
                user_id=save_action.user_id,
                metadata=save_action.metadata,
                tokens_used=save_action.tokens_used,
                processing_time_ms=save_action.processing_time_ms
            )
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "message_id": message.id,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error guardando mensaje: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
    
    async def handle_get_history(self, action: DomainAction) -> Dict[str, Any]:
        """Maneja obtención de historial."""
        start_time = time.time()
        
        try:
            # Convertir a tipo específico
            retrieve_action = ConversationRetrieveAction.parse_obj(action.dict())
            
            # Obtener historial
            messages = await self.conversation_service.get_conversation_history(
                session_id=retrieve_action.session_id,
                tenant_id=retrieve_action.tenant_id,
                limit=retrieve_action.limit,
                include_system=retrieve_action.include_system
            )
            
            # Formatear mensajes para respuesta
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "id": msg.id,
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "metadata": msg.metadata
                })
            
            return {
                "success": True,
                "messages": formatted_messages,
                "total": len(formatted_messages),
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo historial: {str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
