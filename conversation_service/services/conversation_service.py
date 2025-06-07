"""
Servicio principal para gestión de conversaciones.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from conversation_service.config.settings import get_settings
from conversation_service.models.conversation_model import Conversation, Message, MessageRole
from conversation_service.models.actions_model import ConversationSaveAction

settings = get_settings()
logger = logging.getLogger(__name__)

class ConversationService:
    """Servicio principal para gestión de conversaciones."""
    
    def __init__(self, redis_client=None, db_client=None):
        """Inicializa el servicio."""
        self.redis = redis_client
        self.db = db_client
        self.cache_ttl = settings.conversation_cache_ttl
    
    async def create_conversation(
        self,
        tenant_id: str,
        session_id: str,
        agent_id: str,
        user_id: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Conversation:
        """Crea una nueva conversación."""
        conversation = Conversation(
            tenant_id=tenant_id,
            session_id=session_id,
            primary_agent_id=agent_id,
            agent_ids=[agent_id],
            user_id=user_id,
            metadata=metadata or {}
        )
        
        # Guardar en cache
        await self._save_to_cache(conversation)
        
        # TODO: Guardar en base de datos
        
        logger.info(f"Conversación creada: {conversation.id}")
        return conversation
    
    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        tokens_used: Optional[int] = None,
        processing_time_ms: Optional[int] = None
    ) -> Message:
        """Guarda un mensaje en la conversación."""
        # Obtener conversación
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversación no encontrada: {conversation_id}")
        
        # Crear mensaje
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            agent_id=agent_id,
            user_id=user_id,
            metadata=metadata or {},
            tokens_used=tokens_used,
            processing_time_ms=processing_time_ms
        )
        
        # Actualizar métricas de conversación
        conversation.message_count += 1
        if tokens_used:
            conversation.total_tokens += tokens_used
        conversation.last_message_at = datetime.utcnow()
        conversation.updated_at = datetime.utcnow()
        
        # Guardar mensaje en cache
        await self._save_message_to_cache(message)
        
        # Actualizar conversación en cache
        await self._save_to_cache(conversation)
        
        # TODO: Guardar en base de datos
        
        # Trigger analytics si está habilitado
        if settings.enable_realtime_analytics:
            await self._trigger_analytics(conversation_id, message)
        
        logger.info(f"Mensaje guardado: {message.id} en conversación {conversation_id}")
        return message
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Obtiene una conversación por ID."""
        # Verificar cache primero
        cached = await self._get_from_cache(conversation_id)
        if cached:
            return cached
        
        # TODO: Buscar en base de datos
        
        return None
    
    async def get_conversation_history(
        self,
        session_id: str,
        tenant_id: str,
        limit: int = 10,
        include_system: bool = False
    ) -> List[Message]:
        """Obtiene historial de conversación por sesión."""
        # Buscar conversación activa para la sesión
        conversation_key = f"session_conversation:{tenant_id}:{session_id}"
        conversation_id = await self.redis.get(conversation_key) if self.redis else None
        
        if not conversation_id:
            return []
        
        # Obtener mensajes de cache
        messages = await self._get_messages_from_cache(
            conversation_id,
            limit,
            include_system
        )
        
        # TODO: Si no hay suficientes en cache, buscar en DB
        
        return messages
    
    async def search_conversations(
        self,
        tenant_id: str,
        filters: Dict[str, Any],
        page: int = 1,
        page_size: int = 20
    ) -> List[Conversation]:
        """Busca conversaciones con filtros."""
        # TODO: Implementar búsqueda en base de datos
        # Por ahora retorna lista vacía
        return []
    
    async def update_conversation_status(
        self,
        conversation_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Actualiza el estado de una conversación."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False
        
        conversation.status = status
        conversation.updated_at = datetime.utcnow()
        
        if status == "completed":
            conversation.completed_at = datetime.utcnow()
        
        if metadata:
            conversation.metadata.update(metadata)
        
        await self._save_to_cache(conversation)
        
        # TODO: Actualizar en base de datos
        
        return True
    
    # Métodos de cache privados
    async def _save_to_cache(self, conversation: Conversation):
        """Guarda conversación en cache."""
        if not self.redis:
            return
        
        cache_key = f"conversation:{conversation.tenant_id}:{conversation.id}"
        await self.redis.setex(
            cache_key,
            self.cache_ttl,
            conversation.json()
        )
        
        # Mapear sesión a conversación
        session_key = f"session_conversation:{conversation.tenant_id}:{conversation.session_id}"
        await self.redis.setex(
            session_key,
            self.cache_ttl,
            conversation.id
        )
    
    async def _get_from_cache(self, conversation_id: str) -> Optional[Conversation]:
        """Obtiene conversación desde cache."""
        if not self.redis:
            return None
        
        # Buscar en todas las claves posibles
        pattern = f"conversation:*:{conversation_id}"
        keys = await self.redis.keys(pattern)
        
        if keys:
            cached_data = await self.redis.get(keys[0])
            if cached_data:
                return Conversation.parse_raw(cached_data)
        
        return None
    
    async def _save_message_to_cache(self, message: Message):
        """Guarda mensaje en cache."""
        if not self.redis:
            return
        
        # Lista de mensajes por conversación
        messages_key = f"messages:{message.conversation_id}"
        await self.redis.lpush(messages_key, message.json())
        
        # Limitar tamaño de la lista
        await self.redis.ltrim(messages_key, 0, settings.max_context_window - 1)
        
        # TTL
        await self.redis.expire(messages_key, self.cache_ttl)
    
    async def _get_messages_from_cache(
        self,
        conversation_id: str,
        limit: int,
        include_system: bool
    ) -> List[Message]:
        """Obtiene mensajes desde cache."""
        if not self.redis:
            return []
        
        messages_key = f"messages:{conversation_id}"
        raw_messages = await self.redis.lrange(messages_key, 0, limit - 1)
        
        messages = []
        for raw in raw_messages:
            try:
                message = Message.parse_raw(raw)
                if not include_system and message.role == MessageRole.SYSTEM:
                    continue
                messages.append(message)
            except Exception as e:
                logger.error(f"Error parseando mensaje: {str(e)}")
        
        return messages
    
    async def _trigger_analytics(self, conversation_id: str, message: Message):
        """Dispara análisis asíncrono de la conversación."""
        # TODO: Encolar tarea de análisis
        logger.debug(f"Analytics triggered para conversación {conversation_id}")
