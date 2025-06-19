"""
Handler para chat simple con RAG integrado.
"""
import logging
import time
import uuid
from typing import Dict, Any

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError
from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from common.models.chat_models import SimpleChatPayload, SimpleChatResponse, ChatMessage

logger = logging.getLogger(__name__)


class SimpleChatHandler(BaseHandler):
    """Handler para modo simple: Chat + RAG integrado."""

    def __init__(
        self,
        query_client: QueryClient,
        conversation_client: ConversationClient,
        settings: ExecutionServiceSettings
    ):
        super().__init__(settings)
        self.query_client = query_client
        self.conversation_client = conversation_client
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle_simple_chat(
        self,
        payload: SimpleChatPayload,  # Usar modelo unificado (tipo de common.models)
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> SimpleChatResponse:  # Retornar modelo unificado
        """
        Ejecuta chat simple delegando al Query Service.
        
        El Query Service se encarga de:
        1. Realizar búsqueda RAG
        2. Enviar chunks a Groq
        3. Retornar respuesta final
        """
        # conversation_id y message_id se mantienen para el registro de conversación local
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        
        try:
            self._logger.info(
                f"Procesando chat simple",
                extra={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id # Usa el conversation_id local para logging
                }
            )

            # No necesita conversión, Query Service espera el mismo modelo
            query_response = await self.query_client.query_simple(
                payload=payload.model_dump(),  # Enviar todo el payload
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id
            )
            
            # Extraer datos de query_response para guardar la conversación.
            # Se asume que query_response es un diccionario con las claves necesarias.
            agent_message_content = query_response["message"]
            response_sources = query_response["sources"]

            # Guardar conversación (fire-and-forget)
            # Se asume que payload.user_message y payload.collection_ids siguen siendo válidos
            # con el nuevo SimpleChatPayload de common.models.
            await self.conversation_client.save_conversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_message=payload.user_message, 
                agent_message=agent_message_content,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                metadata={
                    "mode": "simple",
                    "collections": payload.collection_ids, 
                    "sources": response_sources
                }
            )

            # Construir respuesta unificada usando datos de query_response
            return SimpleChatResponse(
                message=query_response["message"],
                sources=query_response["sources"],
                usage=query_response["usage"],
                query_id=query_response["query_id"],
                conversation_id=conversation_id, # Se usa el conversation_id generado localmente
                execution_time_ms=query_response["execution_time_ms"]
            )

        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error en simple chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat simple: {str(e)}")