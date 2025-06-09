"""
Handlers para Domain Actions.
"""

import logging
from typing import Dict, Any, Optional
import time

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from conversation_service.models.actions_model import (
    SaveMessageAction, GetContextAction, SessionClosedAction, GetHistoryAction
)
from conversation_service.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

class ConversationHandler:
    """Handler principal para acciones de conversación."""
    
    def __init__(self, conversation_service: ConversationService):
        self.conversation_service = conversation_service
    
    async def handle_save_message(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Maneja guardado de mensajes con soporte para contexto de ejecución."""
        start_time = time.time()
        
        try:
            save_action = SaveMessageAction.parse_obj(action.dict())
            
            # Enriquecer con datos de contexto si está disponible
            tenant_tier = None
            if context:
                tenant_tier = context.tenant_tier
                logger.info(f"Guardando mensaje con contexto. Tier: {tenant_tier}")
                
            result = await self.conversation_service.save_message(
                tenant_id=save_action.tenant_id,
                session_id=save_action.session_id,
                role=save_action.role,
                content=save_action.content,
                agent_id=save_action.agent_id,
                model_name=save_action.model_name,
                user_id=save_action.user_id,
                tokens_estimate=save_action.tokens_estimate,
                metadata=save_action.metadata,
                tenant_tier=tenant_tier
            )
            
            result["execution_time"] = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_save_message: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def handle_get_context(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Maneja obtención de contexto con soporte para contexto de ejecución."""
        start_time = time.time()
        
        try:
            context_action = GetContextAction.parse_obj(action.dict())
            
            # Usar tenant_tier desde ExecutionContext si está disponible
            tenant_tier = context_action.tenant_tier
            if context and context.tenant_tier:
                tenant_tier = context.tenant_tier
                logger.info(f"Obteniendo contexto con tier desde ExecutionContext: {tenant_tier}")
            
            conversation_context = await self.conversation_service.get_context_for_query(
                tenant_id=context_action.tenant_id,
                session_id=context_action.session_id,
                model_name=context_action.model_name,
                tenant_tier=tenant_tier
            )
            
            return {
                "success": True,
                "context": conversation_context.dict(),
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en handle_get_context: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    async def handle_session_closed(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Maneja cierre de sesión con soporte para contexto de ejecución."""
        start_time = time.time()
        
        try:
            close_action = SessionClosedAction.parse_obj(action.dict())
            
            # Usar datos de contexto si está disponible
            if context:
                logger.info(f"Cerrando sesión con contexto de tier: {context.tenant_tier}")
            
            # TODO: Implementar lógica de cierre
            logger.info(f"Cerrando sesión: {close_action.session_id}")
            
            return {
                "success": True,
                "message": "Sesión cerrada correctamente",
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en handle_session_closed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
            
    async def handle_get_history(self, action: DomainAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """Maneja solicitudes de historial de conversación con patrón pseudo-síncrono Redis.
        
        Este método implementa el patrón de request-response sobre Redis que reemplaza
        las llamadas HTTP directas entre servicios.
        
        Args:
            action: Acción de solicitud de historial con correlation_id
            context: Contexto opcional de ejecución
            
        Returns:
            Resultado con mensajes de la conversación
        """
        start_time = time.time()
        
        try:
            history_action = GetHistoryAction.parse_obj(action.dict())
            correlation_id = history_action.correlation_id
            
            # Enriquecer con datos de contexto si está disponible
            tenant_tier = None
            if context:
                tenant_tier = context.tenant_tier
                logger.info(f"Obteniendo historial con tier: {tenant_tier}")
            
            # Obtener historial de conversación
            messages = await self.conversation_service.get_conversation_history(
                tenant_id=history_action.tenant_id,
                session_id=history_action.session_id,
                limit=history_action.limit,
                include_system=history_action.include_system
            )
            
            result = {
                "success": True,
                "data": {
                    "messages": messages
                },
                "correlation_id": correlation_id,
                "execution_time": time.time() - start_time
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_get_history: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "correlation_id": action.correlation_id if hasattr(action, 'correlation_id') else None,
                "execution_time": time.time() - start_time
            }
