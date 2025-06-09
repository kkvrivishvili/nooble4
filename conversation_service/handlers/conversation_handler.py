"""
Handlers para Domain Actions.
"""

import logging
from typing import Dict, Any, Optional
import time

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from conversation_service.models.actions_model import (
    SaveMessageAction, GetContextAction, SessionClosedAction
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
            session_action = SessionClosedAction.parse_obj(action.dict())
            
            success = await self.conversation_service.mark_session_closed(
                session_id=session_action.session_id,
                tenant_id=session_action.tenant_id
            )
            
            return {
                "success": success,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en handle_session_closed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
