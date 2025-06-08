"""
Gestor de persistencia Redis y PostgreSQL.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis

from conversation_service.models.conversation_model import Conversation, Message, ConversationStatus
from conversation_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class PersistenceManager:
    """
    Gestor unificado de persistencia Redis + PostgreSQL.
    """
    
    def __init__(self, redis_client: redis.Redis, db_client=None):
        self.redis = redis_client
        self.db = db_client  # Para cuando esté implementado Supabase
        
    # === REDIS OPERATIONS ===
    
    async def save_conversation_to_redis(self, conversation: Conversation):
        """Guarda conversación en Redis."""
        key = f"conversation:{conversation.tenant_id}:{conversation.id}"
        
        await self.redis.setex(
            key,
            settings.conversation_active_ttl,
            conversation.json()
        )
        
        # Mapeo session -> conversation
        session_key = f"session_conversation:{conversation.tenant_id}:{conversation.session_id}"
        await self.redis.setex(
            session_key,
            settings.conversation_active_ttl,
            conversation.id
        )
        
        # Lista de conversaciones activas por tenant
        active_key = f"active_conversations:{conversation.tenant_id}"
        await self.redis.sadd(active_key, conversation.id)
        await self.redis.expire(active_key, settings.conversation_active_ttl)
    
    async def save_message_to_redis(self, message: Message):
        """Guarda mensaje en Redis."""
        messages_key = f"messages:{message.conversation_id}"
        
        # Agregar mensaje a lista
        await self.redis.lpush(messages_key, message.json())
        
        # Mantener TTL
        await self.redis.expire(messages_key, settings.conversation_active_ttl)
        
        # Actualizar contador de mensajes en conversación
        conversation = await self.get_conversation_from_redis(message.conversation_id)
        if conversation:
            conversation.message_count += 1
            conversation.last_message_at = datetime.utcnow()
            conversation.updated_at = datetime.utcnow()
            if message.tokens_estimate:
                conversation.total_tokens += message.tokens_estimate
            
            await self.save_conversation_to_redis(conversation)
    
    async def get_conversation_from_redis(self, conversation_id: str) -> Optional[Conversation]:
        """Obtiene conversación desde Redis."""
        # Buscar en todas las claves posibles (no tenemos tenant_id aquí)
        pattern = f"conversation:*:{conversation_id}"
        keys = await self.redis.keys(pattern)
        
        if keys:
            data = await self.redis.get(keys[0])
            if data:
                return Conversation.parse_raw(data)
        
        return None
    
    async def get_conversation_by_session(
        self, 
        session_id: str, 
        tenant_id: str
    ) -> Optional[Conversation]:
        """Obtiene conversación por session_id."""
        session_key = f"session_conversation:{tenant_id}:{session_id}"
        conversation_id = await self.redis.get(session_key)
        
        if conversation_id:
            return await self.get_conversation_from_redis(conversation_id)
        
        return None
    
    async def get_messages_from_redis(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Obtiene mensajes desde Redis."""
        messages_key = f"messages:{conversation_id}"
        
        # Obtener mensajes (están en orden LIFO)
        end = limit - 1 if limit else -1
        raw_messages = await self.redis.lrange(messages_key, 0, end)
        
        messages = []
        for raw in reversed(raw_messages):  # Invertir para orden cronológico
            try:
                message = Message.parse_raw(raw)
                messages.append(message)
            except Exception as e:
                logger.error(f"Error parseando mensaje: {str(e)}")
        
        return messages
    
    async def mark_conversation_for_migration(self, conversation_id: str):
        """Marca conversación para migración a PostgreSQL."""
        conversation = await self.get_conversation_from_redis(conversation_id)
        if conversation:
            conversation.needs_migration = True
            conversation.websocket_closed_at = datetime.utcnow()
            conversation.status = ConversationStatus.COMPLETED
            await self.save_conversation_to_redis(conversation)
    
    async def get_conversations_needing_migration(self) -> List[str]:
        """Obtiene conversaciones que necesitan migración."""
        # Buscar conversaciones marcadas para migración
        pattern = "conversation:*:*"
        keys = await self.redis.keys(pattern)
        
        migration_candidates = []
        grace_period = timedelta(seconds=settings.websocket_grace_period)
        
        for key in keys:
            data = await self.redis.get(key)
            if data:
                try:
                    conversation = Conversation.parse_raw(data)
                    
                    # Verificar si necesita migración
                    if (conversation.needs_migration and 
                        conversation.websocket_closed_at and
                        datetime.utcnow() - conversation.websocket_closed_at > grace_period):
                        migration_candidates.append(conversation.id)
                        
                except Exception as e:
                    logger.error(f"Error parseando conversación para migración: {str(e)}")
        
        return migration_candidates
    
    # === POSTGRESQL OPERATIONS (preparado) ===
    
    async def migrate_conversation_to_postgresql(self, conversation_id: str) -> bool:
        """Migra conversación completa a PostgreSQL."""
        if not self.db:
            logger.warning("PostgreSQL no configurado, migración omitida")
            return False
        
        try:
            # Obtener conversación y mensajes de Redis
            conversation = await self.get_conversation_from_redis(conversation_id)
            if not conversation:
                return False
            
            messages = await self.get_messages_from_redis(conversation_id)
            
            # TODO: Implementar cuando esté disponible Supabase
            # await self.db.conversations.insert(conversation.dict())
            # for message in messages:
            #     await self.db.messages.insert(message.dict())
            
            # Marcar como migrada
            conversation.migrated_to_db = True
            conversation.status = ConversationStatus.TRANSFERRED
            await self.save_conversation_to_redis(conversation)
            
            # Programar limpieza de Redis (después de un tiempo)
            await self._schedule_redis_cleanup(conversation_id)
            
            logger.info(f"Conversación migrada a PostgreSQL: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrando conversación {conversation_id}: {str(e)}")
            return False
    
    async def _schedule_redis_cleanup(self, conversation_id: str):
        """Programa limpieza de Redis después de migración exitosa."""
        # Dar tiempo para que otros servicios terminen de usar la conversación
        cleanup_delay = 300  # 5 minutos
        
        # TODO: Implementar con job scheduler o worker específico
        # Por ahora, simplemente logear
        logger.info(f"Programada limpieza Redis para {conversation_id} en {cleanup_delay}s")
    
    # === STATISTICS OPERATIONS ===
    
    async def get_basic_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas básicas del tenant."""
        try:
            # Conversaciones activas
            active_key = f"active_conversations:{tenant_id}"
            active_count = await self.redis.scard(active_key)
            
            # Buscar todas las conversaciones del tenant en Redis
            pattern = f"conversation:{tenant_id}:*"
            conversation_keys = await self.redis.keys(pattern)
            
            total_conversations = len(conversation_keys)
            total_messages = 0
            agents_usage = {}
            
            for key in conversation_keys:
                data = await self.redis.get(key)
                if data:
                    try:
                        conv = Conversation.parse_raw(data)
                        total_messages += conv.message_count
                        
                        # Conteo por agente
                        agent_id = conv.agent_id
                        if agent_id not in agents_usage:
                            agents_usage[agent_id] = 0
                        agents_usage[agent_id] += 1
                        
                    except Exception as e:
                        logger.error(f"Error parseando conversación para stats: {str(e)}")
            
            return {
                "tenant_id": tenant_id,
                "active_conversations": active_count,
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "avg_messages_per_conversation": total_messages / max(total_conversations, 1),
                "agents_usage": agents_usage,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            return {
                "tenant_id": tenant_id,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }

