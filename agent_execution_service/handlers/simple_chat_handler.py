"""
Handler para procesamiento simple de chat usando QueryService.

Maneja conversaciones simples sin herramientas ni ReAct loops.
Delega la gestión de conversaciones al ConversationHelper.
"""
import logging
import uuid
from typing import List

from common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from common.clients.redis import CacheManager
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from .conversation_handler import ConversationHelper


logger = logging.getLogger(__name__)


class SimpleChatHandler:
    """
    Handler para procesamiento simple de chat.
    
    Maneja conversaciones directas con el LLM sin herramientas,
    usando ConversationHelper para gestión de historial.
    """
    
    def __init__(
        self,
        query_client: QueryClient,
        conversation_client: ConversationClient,
        settings,
        redis_conn
    ):
        """
        Inicializa SimpleChatHandler.
        
        Args:
            query_client: Cliente para consultas al LLM
            conversation_client: Cliente para persistencia de conversaciones
            settings: Configuración del servicio
            redis_conn: Conexión directa a Redis
        """
        self.query_client = query_client
        self.conversation_client = conversation_client
        self.settings = settings
        
        # Inicializar CacheManager
        self.cache_manager = CacheManager(
            redis_conn=redis_conn,
            service_name="agent_execution"
        )
        
        # Inicializar ConversationHelper
        self.conversation_helper = ConversationHelper(
            cache_manager=self.cache_manager,
            conversation_client=self.conversation_client
        )
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def handle_simple_chat(
        self,
        payload: Dict[str, Any],
        execution_config,
        query_config,
        rag_config,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID
    ) -> ChatResponse:
        """
        Maneja una solicitud de chat simple con configuración explícita.
        
        Args:
            payload: Datos de la solicitud de chat
            execution_config: Configuración de ejecución
            query_config: Configuración para Query Service
            rag_config: Configuración para RAG
            tenant_id: ID del tenant
            session_id: ID de la sesión
            task_id: ID de la tarea
            agent_id: ID del agente
            
        Returns:
            Respuesta del chat
        """
        # Parsear ChatRequest
        chat_request = ChatRequest.model_validate(payload)
        chat_request.tenant_id = tenant_id
        chat_request.session_id = session_id
        chat_request.task_id = task_id
        chat_request.agent_id = agent_id
        
        # Procesar el chat con la configuración recibida
        return await self._process_chat(chat_request, execution_config)
        
    async def _process_chat(self, chat_request: ChatRequest, execution_config) -> ChatResponse:
        """
        Procesa una solicitud de chat simple.
        
        Args:
            chat_request: Solicitud de chat con mensajes y metadatos
            
        Returns:
            Respuesta del chat con el mensaje generado
        """
        try:
            self.logger.info(
                "Iniciando procesamiento de chat simple",
                extra={
                    "tenant_id": str(chat_request.tenant_id),
                    "session_id": str(chat_request.session_id),
                    "agent_id": str(chat_request.agent_id),
                    "task_id": str(chat_request.task_id),
                    "messages_count": len(chat_request.messages)
                }
            )
            
            # 1. Obtener o crear conversación
            history = await self.conversation_helper.get_or_create_conversation(
                tenant_id=chat_request.tenant_id,
                session_id=chat_request.session_id,
                agent_id=chat_request.agent_id
            )
            
            # 2. Separar mensajes por tipo
            system_messages = [msg for msg in chat_request.messages if msg.role == "system"]
            user_messages = [msg for msg in chat_request.messages if msg.role == "user"]
            
            # 3. Integrar historial con mensajes nuevos
            integrated_messages = self.conversation_helper.integrate_history_with_messages(
                history=history,
                system_messages=system_messages,
                user_messages=user_messages
            )
            
            # 4. Preparar payload para query service
            payload = {
                "messages": [msg.dict() for msg in integrated_messages],
                "agent_id": str(chat_request.agent_id),
                "session_id": str(chat_request.session_id),
                "task_id": str(chat_request.task_id)
            }
            
            self.logger.debug(
                "Payload preparado para query service",
                extra={
                    "agent_id": str(chat_request.agent_id),
                    "total_messages": len(integrated_messages),
                    "task_id": str(chat_request.task_id)
                }
            )
            
            # 5. Enviar consulta al LLM
            query_response = await self.query_client.query_simple(payload)
            
            # 6. Crear respuesta
            response_message = ChatMessage(
                role="assistant",
                content=query_response["response"]
            )
            
            chat_response = ChatResponse(
                message=response_message,
                conversation_id=history.conversation_id,
                metadata={
                    "mode": "simple",
                    "total_messages": len(integrated_messages),
                    **chat_request.metadata
                }
            )
            
            # 7. Extraer último mensaje de usuario para guardar
            last_user_message = user_messages[-1] if user_messages else ChatMessage(
                role="user", 
                content="[Sin mensaje de usuario]"
            )
            
            # 8. Guardar intercambio completo
            await self.conversation_helper.save_conversation_exchange(
                tenant_id=chat_request.tenant_id,
                session_id=chat_request.session_id,
                agent_id=chat_request.agent_id,
                history=history,
                user_message=last_user_message,
                assistant_message=response_message,
                task_id=chat_request.task_id,
                ttl=execution_config.history_ttl,
                metadata={
                    "mode": "simple",
                    "query_service_response": query_response
                }
            )
            
            self.logger.info(
                "Chat simple procesado exitosamente",
                extra={
                    "conversation_id": history.conversation_id,
                    "task_id": str(chat_request.task_id),
                    "response_length": len(response_message.content)
                }
            )
            
            return chat_response
            
        except Exception as e:
            self.logger.error(
                "Error procesando chat simple",
                extra={
                    "tenant_id": str(chat_request.tenant_id),
                    "session_id": str(chat_request.session_id),
                    "agent_id": str(chat_request.agent_id),
                    "task_id": str(chat_request.task_id),
                    "error": str(e)
                }
            )
            raise