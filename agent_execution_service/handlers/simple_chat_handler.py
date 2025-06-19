"""
Handler para chat simple con RAG integrado.
"""
import logging
import time
import uuid
from typing import Dict, Any

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import SimpleChatPayload, SimpleChatResponse

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..models.execution_payloads import ExecutionSimpleChatPayload


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

    async def handle_simple_chat(
        self,
        payload: ExecutionSimpleChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> SimpleChatResponse:
        """
        Ejecuta chat simple delegando al Query Service.
        """
        start_time = time.time()
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        
        try:
            self.logger.info(
                f"Procesando chat simple",
                extra={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "request_id": payload.request_id
                }
            )

            # Crear payload base sin campos específicos de Execution
            query_payload = SimpleChatPayload(
                user_message=payload.user_message,
                chat_model=payload.chat_model,
                system_prompt=payload.system_prompt,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                top_p=payload.top_p,
                frequency_penalty=payload.frequency_penalty,
                presence_penalty=payload.presence_penalty,
                stop=payload.stop,
                embedding_model=payload.embedding_model,
                embedding_dimensions=payload.embedding_dimensions,
                collection_ids=payload.collection_ids,
                document_ids=payload.document_ids,
                top_k=payload.top_k,
                similarity_threshold=payload.similarity_threshold,
                conversation_history=payload.conversation_history
            )

            # Delegar al Query Service
            query_response = await self.query_client.query_simple(
                payload=query_payload.model_dump(),
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id
            )

            # Parsear respuesta
            response = SimpleChatResponse.model_validate(query_response)
            
            # Actualizar conversation_id con el nuestro
            response.conversation_id = conversation_id

            # Guardar conversación (fire-and-forget)
            await self.conversation_client.save_conversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_message=payload.user_message,
                agent_message=response.message,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                metadata={
                    "mode": "simple",
                    "collections": payload.collection_ids,
                    "sources": response.sources,
                    "request_id": payload.request_id,
                    "client_metadata": payload.client_metadata,
                    "token_usage": response.usage.model_dump()
                }
            )

            return response

        except ExternalServiceError:
            raise
        except Exception as e:
            self.logger.error(f"Error en simple chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat simple: {str(e)}")