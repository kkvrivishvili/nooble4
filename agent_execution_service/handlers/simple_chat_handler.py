"""
Handler para chat simple con RAG integrado.
"""
import logging
import time
import uuid
from typing import Dict, Any, Optional

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, RAGConfig, ConversationHistory
from common.clients.redis.redis_state_manager import RedisStateManager

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient


class SimpleChatHandler(BaseHandler):
    """Handler para modo simple: Chat + RAG integrado."""

    def __init__(
        self,
        query_client: QueryClient,
        conversation_client: ConversationClient,
        settings: ExecutionServiceSettings,
        redis_conn
    ):
        super().__init__(settings)
        self.query_client = query_client
        self.conversation_client = conversation_client
        self.redis_conn = redis_conn
        
        # State manager para el historial
        self.history_manager = RedisStateManager[ConversationHistory](
            redis_conn=redis_conn,
            state_model=ConversationHistory,
            app_settings=settings
        )

    async def handle_simple_chat(
        self,
        payload: Dict[str, Any],
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID,
        agent_id: Optional[str] = None  # NUEVO: recibir agent_id como parámetro
    ) -> ChatResponse:
        """
        Ejecuta chat simple delegando al Query Service.
        Maneja cache de historial localmente.
        """
        start_time = time.time()
        
        try:
            # Parsear el ChatRequest
            chat_request = ChatRequest.model_validate(payload)
            
            # Usar agent_id del header o default
            if not agent_id:
                agent_id = "default-agent"
                self.logger.warning("No se proporcionó agent_id, usando default")
            
            # Construir key para cache
            cache_key = self._build_cache_key(tenant_id, session_id)
            
            # Intentar recuperar historial de cache
            history = await self.history_manager.load_state(cache_key)
            
            # Determinar conversation_id
            if history:
                conversation_id = history.conversation_id
                
                # Validar que el agent_id coincida
                if history.agent_id != agent_id:
                    self.logger.warning(
                        f"Agent_id cambió en la conversación: {history.agent_id} -> {agent_id}"
                    )
                
                # Integrar mensajes históricos
                system_messages = [msg for msg in chat_request.messages if msg.role == "system"]
                user_messages = [msg for msg in chat_request.messages if msg.role == "user"]
                
                # Reconstruir: system + historial + nuevo user
                integrated_messages = system_messages + history.to_chat_messages() + user_messages
                chat_request.messages = integrated_messages
                
                self.logger.info(
                    f"Historial integrado desde cache",
                    extra={
                        "conversation_id": conversation_id,
                        "historical_messages": len(history.messages),
                        "total_messages": len(integrated_messages),
                        "agent_id": agent_id
                    }
                )
            else:
                # Nueva conversación
                conversation_id = str(uuid.uuid4())
                history = ConversationHistory(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    agent_id=agent_id
                )
                self.logger.info(f"Nueva conversación iniciada: {conversation_id} para agent: {agent_id}")

            # Delegar al Query Service - pasando agent_id en el header
            query_response = await self.query_client.query_simple(
                payload=chat_request.model_dump(),
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id  # NUEVO: pasar agent_id
            )

            # Parsear respuesta
            response = ChatResponse.model_validate(query_response)
            response.conversation_id = conversation_id

            # Actualizar historial en cache local
            user_message = next(
                (msg for msg in reversed(chat_request.messages) if msg.role == "user"),
                None
            )
            
            if user_message and response.message:
                # Agregar mensajes al historial
                history.add_message(user_message)
                history.add_message(response.message)
                
                # Guardar en cache con TTL de 30 minutos
                await self.history_manager.save_state(
                    cache_key,
                    history,
                    expiration_seconds=1800  # 30 minutos
                )
                
                # Enviar a Conversation Service para persistencia (fire-and-forget)
                # NO incluir IDs que ya van en el header
                await self.conversation_client.save_conversation(
                    conversation_id=conversation_id,
                    message_id=str(uuid.uuid4()),
                    user_message=user_message.content,
                    agent_message=response.message.content,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,  # Ahora va en el header
                    metadata={
                        "mode": "simple",
                        "collections": chat_request.rag_config.collection_ids if chat_request.rag_config else [],
                        "sources": response.sources,
                        "token_usage": response.usage.model_dump()
                    }
                )

            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error en simple chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat simple: {str(e)}")
    
    def _build_cache_key(self, tenant_id: str, session_id: str) -> str:
        """Construye la key de cache siguiendo el patrón estándar."""
        prefix = "nooble4"
        environment = self.app_settings.environment
        return f"{prefix}:{environment}:agent_execution:history:{tenant_id}:{session_id}"