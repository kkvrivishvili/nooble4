"""
Servicio principal integrado con MemoryManager y PersistenceManager.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from conversation_service.models.conversation_model import (
    Conversation, Message, MessageRole, ConversationContext
)
from conversation_service.services.memory_manager import MemoryManager
from conversation_service.services.persistence_manager import PersistenceManager
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ConversationService:
    """
    Servicio principal para la gestión de conversaciones.
    """
    
    def __init__(self, redis_client, db_client=None):
        self.persistence = PersistenceManager(redis_client, db_client)
        self.memory_manager = MemoryManager()
        
    # === CORE OPERATIONS ===
    
    async def save_message(
        self,
        tenant_id: str,
        session_id: str,
        role: str,
        content: str,
        agent_id: str,
        model_name: str = "llama3-8b-8192",
        user_id: Optional[str] = None,
        tokens_estimate: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Guarda un nuevo mensaje en una conversación.
        """
        try:
            # Buscar o crear conversación
            conversation = await self.persistence.get_conversation_by_session(session_id, tenant_id)
            
            if not conversation:
                # Crear nueva conversación
                conversation = Conversation(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    model_name=model_name
                )
                await self.persistence.save_conversation_to_redis(conversation)
                logger.info(f"Nueva conversación creada: {conversation.id}")
            
            # Crear mensaje
            message = Message(
                conversation_id=conversation.id,
                role=MessageRole(role),
                content=content,
                agent_id=agent_id,
                model_used=model_name,
                tokens_estimate=tokens_estimate or self._estimate_tokens(content),
                metadata=metadata or {}
            )
            
            # Guardar en Redis
            await self.persistence.save_message_to_redis(message)
            
            # La gestión de memoria ahora es más simple y no requiere una actualización explícita aquí.
            # El contexto se construye directamente desde los mensajes guardados cuando se solicita.
            
            logger.info(f"Mensaje guardado: {message.id} en conversación {conversation.id}")
            
            return {
                "success": True,
                "conversation_id": conversation.id,
                "message_id": message.id,
                "tokens_used": message.tokens_estimate
            }
            
        except Exception as e:
            logger.error(f"Error guardando mensaje: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_context_for_query(
        self,
        tenant_id: str,
        session_id: str,
        model_name: str = "llama3-8b-8192",
        tenant_tier: str = "free"
    ) -> ConversationContext:
        """
        Obtiene contexto optimizado para Query Service.
        """
        try:
            # Buscar conversación
            conversation = await self.persistence.get_conversation_by_session(session_id, tenant_id)
            
            if not conversation:
                return ConversationContext(
                    conversation_id="",
                    messages=[],
                    total_tokens=0,
                    model_name=model_name,
                    truncation_applied=False
                )
            
            # Obtener contexto desde el gestor de memoria
            context_data = self.memory_manager.get_context_for_query(
                conversation.id,
                model_name,
                tenant_tier
            )
            
            return ConversationContext(
                conversation_id=conversation.id,
                messages=context_data["messages"],
                total_tokens=context_data["total_tokens"],
                model_name=model_name,
                truncation_applied=context_data["truncation_applied"]
            )
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto: {str(e)}")
            return ConversationContext(
                conversation_id="",
                messages=[],
                total_tokens=0,
                model_name=model_name,
                truncation_applied=False
            )
    
    async def mark_session_closed(self, session_id: str, tenant_id: str) -> bool:
        """
        Marca sesión como cerrada para posterior migración.
        """
        try:
            conversation = await self.persistence.get_conversation_by_session(session_id, tenant_id)
            
            if conversation:
                await self.persistence.mark_conversation_for_migration(conversation.id)
                logger.info(f"Sesión marcada para migración: {session_id}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error marcando sesión cerrada: {str(e)}")
            return False
    
    # === STATISTICS AND ADMIN ===
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas del tenant."""
        return await self.persistence.get_basic_stats(tenant_id)
    
    async def get_conversation_list(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Lista conversaciones para CRM/Dashboard.
        """
        try:
            # TODO: Implementar cuando esté PostgreSQL
            # Por ahora, buscar en Redis (solo activas)
            pattern = f"conversation:{tenant_id}:*"
            keys = await self.persistence.redis.keys(pattern)
            
            conversations = []
            for key in keys[:limit]:
                data = await self.persistence.redis.get(key)
                if data:
                    try:
                        conv = Conversation.parse_raw(data)
                        
                        # Filtrar por agente si se especifica
                        if agent_id and conv.agent_id != agent_id:
                            continue
                        
                        conversations.append({
                            "id": conv.id,
                            "session_id": conv.session_id,
                            "agent_id": conv.agent_id,
                            "status": conv.status.value,
                            "message_count": conv.message_count,
                            "total_tokens": conv.total_tokens,
                            "created_at": conv.created_at.isoformat(),
                            "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None
                        })
                        
                    except Exception as e:
                        logger.error(f"Error parseando conversación: {str(e)}")
            
            # Ordenar por fecha de creación (más reciente primero)
            conversations.sort(key=lambda x: x["created_at"], reverse=True)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error listando conversaciones: {str(e)}")
            return []
    
    async def get_conversation_full(self, conversation_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Obtiene conversación completa con mensajes para CRM.
        """
        try:
            conversation = await self.persistence.get_conversation_from_redis(conversation_id)
            
            # Verificar pertenencia al tenant
            if not conversation or conversation.tenant_id != tenant_id:
                return {"error": "Conversación no encontrada"}
            
            # Obtener mensajes
            messages = await self.persistence.get_messages_from_redis(conversation_id)
            
            return {
                "conversation": {
                    "id": conversation.id,
                    "session_id": conversation.session_id,
                    "agent_id": conversation.agent_id,
                    "user_id": conversation.user_id,
                    "status": conversation.status.value,
                    "created_at": conversation.created_at.isoformat(),
                    "message_count": conversation.message_count,
                    "total_tokens": conversation.total_tokens
                },
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                        "tokens_estimate": msg.tokens_estimate,
                        "agent_id": msg.agent_id,
                        "model_used": msg.model_used
                    }
                    for msg in messages
                ]
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo conversación completa: {str(e)}")
            return {"error": str(e)}
    
    # === HELPER METHODS ===
    
    def _estimate_tokens(self, content: str) -> int:
        """Estimación simple de tokens."""
        # Aproximación: 1 token ≈ 0.75 palabras para español
        words = len(content.split())
        return int(words * 1.33)
    
    def _extract_tier_from_metadata(self, metadata: Dict[str, Any]) -> str:
        """Extrae tier desde metadata o usa default."""
        if metadata and "tenant_tier" in metadata:
            return metadata["tenant_tier"]
        return "free"
