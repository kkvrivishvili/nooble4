"""
Handler para chat simple con RAG integrado.
"""
import logging
import time
import uuid
from typing import Dict, Any

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig
from common.clients.redis.redis_state_manager import RedisStateManager

from common.config.service_settings import ExecutionServiceSettings
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
        execution_config: ExecutionConfig,
        query_config: QueryConfig,
        rag_config: RAGConfig,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID
    ) -> ChatResponse:
        """
        Ejecuta chat simple delegando al Query Service.
        Maneja cache de historial localmente.
        """
        start_time = time.time()
        
        try:
            # Parsear el ChatRequest
            chat_request = ChatRequest.model_validate(payload)
            
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

            # Preparar payload limpio para query_service (solo datos de chat)
            query_payload = {
                "messages": chat_request.messages  # Con historial integrado
            }

            # Delegar al Query Service con configuraciones explícitas
            query_response = await self.query_client.query_simple(
                payload=query_payload,
                query_config=query_config,  # Config explícita
                rag_config=rag_config,      # Config explícita
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id
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
                
                # Guardar en cache usando conversation_cache_ttl de execution_config
                await self.history_manager.save_state(
                    cache_key,
                    history,
                    expiration_seconds=execution_config.conversation_cache_ttl
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
                    agent_id=agent_id,
                    metadata={
                        "mode": "simple",
                        "collections": rag_config.collection_ids if rag_config else [],
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
    
    def _build_cache_key(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> str:
        """Construye la key de cache siguiendo el patrón estándar."""
        prefix = "nooble4"
        environment = self.app_settings.environment
        return f"{prefix}:{environment}:agent_execution:history:{tenant_id}:{session_id}"