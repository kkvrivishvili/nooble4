"""
Helper especializado para gestión completa del ciclo de vida de conversaciones.

Maneja:
- Identificación única por tenant + session + agent
- Recuperación desde cache con ID determinístico
- Persistencia dual (cache + Conversation Service)
- Integración de historial con mensajes nuevos
"""
import logging
import uuid
from typing import Optional, List

from common.models.chat_models import ConversationHistory, ChatMessage
from common.clients.redis.cache_manager import CacheManager
from ..clients.conversation_client import ConversationClient


class ConversationHelper:
    """
    Helper para gestión de conversaciones en SimpleChatHandler y AdvanceChatHandler.
    
    Responsabilidades:
    - Generar conversation_id determinístico
    - Recuperar/crear conversaciones desde cache
    - Integrar historial con mensajes nuevos
    - Guardar en cache y Conversation Service
    """
    
    def __init__(
        self,
        cache_manager: 'CacheManager[ConversationHistory]',
        conversation_client: ConversationClient
    ):
        """
        Inicializa el ConversationHelper.
        
        Args:
            cache_manager: Gestor genérico de cache
            conversation_client: Cliente para persistencia en Conversation Service
        """
        self.cache_manager = cache_manager
        self.conversation_client = conversation_client
        self._logger = logging.getLogger(f"{__name__}.ConversationHelper")
    
    def generate_conversation_id(
        self, 
        tenant_id: uuid.UUID, 
        session_id: uuid.UUID, 
        agent_id: uuid.UUID
    ) -> str:
        """
        Genera conversation_id determinístico basado en tenant + session + agent.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            agent_id: ID del agente
            
        Returns:
            conversation_id determinístico como string
        """
        combined = f"{tenant_id}:{session_id}:{agent_id}"
        conversation_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, combined))
        
        self._logger.debug(
            "Conversation ID generado determinísticamente",
            extra={
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "agent_id": str(agent_id),
                "conversation_id": conversation_id
            }
        )
        
        return conversation_id
    
    async def get_or_create_conversation(
        self,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        agent_id: uuid.UUID
    ) -> ConversationHistory:
        """
        Obtiene conversación existente desde cache o crea una nueva.
        
        Usa conversation_id determinístico para garantizar consistencia
        incluso si el cache expira.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            agent_id: ID del agente
            
        Returns:
            ConversationHistory (existente o nueva)
        """
        conversation_id = self.generate_conversation_id(tenant_id, session_id, agent_id)
        
        self._logger.info(
            "Recuperando/creando conversación",
            extra={
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "agent_id": str(agent_id),
                "conversation_id": conversation_id
            }
        )
        
        # Recuperar desde cache usando contexto con agent_id
        context = [str(tenant_id), str(session_id), str(agent_id)]
        history = await self.cache_manager.get("history", context)
        
        if history:
            # Validar conversation_id por consistencia
            if history.conversation_id != conversation_id:
                self._logger.warning(
                    "Conversation ID en cache no coincide con determinístico, actualizando",
                    extra={
                        "cached_id": history.conversation_id,
                        "deterministic_id": conversation_id
                    }
                )
                history.conversation_id = conversation_id
            
            self._logger.info(
                "Conversación recuperada desde cache",
                extra={
                    "conversation_id": conversation_id,
                    "messages_count": len(history.messages)
                }
            )
            return history
        
        # Crear nueva conversación
        history = ConversationHistory(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id
        )
        
        self._logger.info(
            "Nueva conversación creada",
            extra={
                "conversation_id": conversation_id,
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "agent_id": str(agent_id)
            }
        )
        
        return history
    
    def integrate_history_with_messages(
        self,
        history: ConversationHistory,
        system_messages: List[ChatMessage],
        user_messages: List[ChatMessage]
    ) -> List[ChatMessage]:
        """
        Integra el historial existente con mensajes nuevos.
        
        Args:
            history: Historial de conversación
            system_messages: Mensajes del sistema
            user_messages: Mensajes del usuario actuales
            
        Returns:
            Lista de mensajes integrados: system + history + user
        """
        # Convertir historial a ChatMessages
        history_messages = history.to_chat_messages()
        
        # Integrar en orden: system -> history -> user
        integrated_messages = system_messages + history_messages + user_messages
        
        self._logger.debug(
            "Historial integrado con mensajes",
            extra={
                "conversation_id": history.conversation_id,
                "system_messages": len(system_messages),
                "history_messages": len(history_messages),
                "user_messages": len(user_messages),
                "total_messages": len(integrated_messages)
            }
        )
        
        return integrated_messages
    
    async def save_conversation_exchange(
        self,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        agent_id: uuid.UUID,
        history: ConversationHistory,
        user_message: ChatMessage,
        assistant_message: ChatMessage,
        task_id: uuid.UUID,
        ttl: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """
        Guarda el intercambio completo (user + assistant) en cache y DB.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            agent_id: ID del agente
            history: Historial de conversación actualizado
            user_message: Mensaje del usuario
            assistant_message: Mensaje del asistente
            task_id: ID de la tarea
            ttl: TTL para cache
            metadata: Metadatos adicionales
        """
        # Agregar mensajes al historial
        history.add_message(user_message)
        history.add_message(assistant_message)
        
        # Guardar en cache
        context = [str(tenant_id), str(session_id), str(agent_id)]
        await self.cache_manager.save("history", context, history, ttl)
        
        self._logger.info(
            "Conversación guardada en cache",
            extra={
                "conversation_id": history.conversation_id,
                "messages_count": len(history.messages),
                "ttl_seconds": ttl
            }
        )
        
        # Guardar en Conversation Service (fire-and-forget)
        try:
            await self.conversation_client.save_conversation(
                conversation_id=history.conversation_id,
                message_id=str(uuid.uuid4()),
                user_message=user_message.content,
                agent_message=assistant_message.content,
                tenant_id=str(tenant_id),
                session_id=str(session_id),
                task_id=task_id,
                agent_id=str(agent_id),
                metadata=metadata or {}
            )
            
            self._logger.info(
                "Conversación guardada en Conversation Service",
                extra={
                    "conversation_id": history.conversation_id,
                    "task_id": str(task_id)
                }
            )
            
        except Exception as e:
            # Fire-and-forget: no fallar si no se puede guardar en DB
            self._logger.error(
                "Error guardando en Conversation Service",
                extra={
                    "conversation_id": history.conversation_id,
                    "error": str(e)
                }
            )
