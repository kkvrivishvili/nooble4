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
from ..models.execution_payloads import SimpleChatPayload
from ..models.execution_responses import SimpleExecutionResponse

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
        payload: SimpleChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> SimpleExecutionResponse:
        """
        Ejecuta chat simple delegando al Query Service.
        
        El Query Service se encarga de:
        1. Realizar búsqueda RAG
        2. Enviar chunks a Groq
        3. Retornar respuesta final
        """
        start_time = time.time()
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        
        try:
            self._logger.info(
                f"Procesando chat simple",
                extra={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id
                }
            )

            # Delegar al Query Service con RAG integrado
            query_response = await self.query_client.query_simple(
                user_message=payload.user_message,
                collection_ids=payload.collection_ids,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                agent_config=agent_config_to_query_format(payload.agent_config),
                embedding_config=payload.embedding_config.model_dump(),
                document_ids=payload.document_ids,
                conversation_history=payload.conversation_history
            )

            # Extraer respuesta y sources del resultado
            agent_message = query_response.get("message", "")
            sources = query_response.get("sources", [])

            # Guardar conversación (fire-and-forget)
            await self.conversation_client.save_conversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_message=payload.user_message,
                agent_message=agent_message,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                metadata={
                    "mode": "simple",
                    "collections": payload.collection_ids,
                    "sources": sources
                }
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return SimpleExecutionResponse(
                message=agent_message,
                sources=sources,
                conversation_id=conversation_id,
                execution_time_ms=execution_time_ms
            )

        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error en simple chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat simple: {str(e)}")