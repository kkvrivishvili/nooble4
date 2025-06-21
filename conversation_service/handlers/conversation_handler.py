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
            # TODOS los IDs vienen del header del DomainAction
            tenant_id = action.tenant_id
            session_id = action.session_id
            agent_id = action.agent_id or "default-agent"  # CORREGIDO: del header, no de metadata
            user_id = action.user_id
            
            # Solo el contenido viene del payload
            conversation_id = action.data.get("conversation_id")
            message_id = action.data.get("message_id")
            user_message = action.data.get("user_message")
            agent_message = action.data.get("agent_message")
            metadata = action.data.get("metadata", {})
            
            # Guardar mensaje del usuario
            result = await self.conversation_service.save_message(
                tenant_id=tenant_id,
                session_id=session_id,
                role="user",
                content=user_message,
                agent_id=agent_id,  # Del header
                model_name=metadata.get("model", "llama3-8b-8192"),
                user_id=user_id,  # Del header
                tokens_estimate=None,
                metadata=metadata,
                tenant_tier=context.tenant_tier if context else "free"
            )
            
            # Guardar mensaje del asistente también
            if agent_message:
                await self.conversation_service.save_message(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    role="assistant",
                    content=agent_message,
                    agent_id=agent_id,  # Del header
                    model_name=metadata.get("model", "llama3-8b-8192"),
                    user_id=user_id,  # Del header
                    tokens_estimate=metadata.get("token_usage", {}).get("completion_tokens"),
                    metadata=metadata,
                    tenant_tier=context.tenant_tier if context else "free"
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
            # No usar parse_obj, usar los datos directamente del DomainAction
            
            # Usar tenant_tier desde ExecutionContext si está disponible
            tenant_tier = "free"
            if context and context.tenant_tier:
                tenant_tier = context.tenant_tier
                logger.info(f"Obteniendo contexto con tier desde ExecutionContext: {tenant_tier}")
            
            conversation_context = await self.conversation_service.get_context_for_query(
                tenant_id=action.tenant_id,  # Del header
                session_id=action.session_id,  # Del header
                model_name=action.data.get("model_name", "llama3-8b-8192"),  # Del payload
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
            # Usar datos del header directamente
            session_id = action.session_id
            tenant_id = action.tenant_id
            
            # Usar datos de contexto si está disponible
            if context:
                logger.info(f"Cerrando sesión con contexto de tier: {context.tenant_tier}")
            
            # Marcar sesión como cerrada para migración
            closed = await self.conversation_service.mark_session_closed(
                session_id=session_id,
                tenant_id=tenant_id
            )
            
            return {
                "success": closed,
                "message": "Sesión marcada para migración" if closed else "Sesión no encontrada",
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
            # Usar datos del header y payload directamente
            tenant_id = action.tenant_id
            session_id = action.session_id
            correlation_id = action.correlation_id
            
            # Datos del payload
            limit = action.data.get("limit", 10)
            include_system = action.data.get("include_system", False)
            
            # Enriquecer con datos de contexto si está disponible
            tenant_tier = None
            if context:
                tenant_tier = context.tenant_tier
                logger.info(f"Obteniendo historial con tier: {tenant_tier}")
            
            # Obtener historial de conversación
            messages = await self.conversation_service.get_conversation_history(
                tenant_id=tenant_id,
                session_id=session_id,
                limit=limit,
                include_system=include_system
            )
            
            result = {
                "success": True,
                "data": {
                    "messages": messages
                },
                "correlation_id": str(correlation_id) if correlation_id else None,
                "execution_time": time.time() - start_time
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error en handle_get_history: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "correlation_id": str(action.correlation_id) if action.correlation_id else None,
                "execution_time": time.time() - start_time
            }