"""
Handler para chat simple con RAG integrado.
"""
import logging
import time
import uuid
from typing import Dict, Any

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, RAGConfig

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient


async def handle_simple_chat(
    self,
    # Cambio: ahora recibe directamente ChatRequest del payload
    payload: Dict[str, Any],  # Este es el action.data
    tenant_id: str,
    session_id: str,
    task_id: uuid.UUID
) -> ChatResponse:
    """
    Ejecuta chat simple delegando al Query Service.
    """
    start_time = time.time()
    conversation_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    try:
        # Parsear el ChatRequest del payload
        chat_request = ChatRequest.model_validate(payload)
        
        self.logger.info(
            f"Procesando chat simple",
            extra={
                "tenant_id": tenant_id,
                "session_id": session_id,
                "conversation_id": conversation_id
            }
        )

        # Delegar al Query Service sin transformación
        query_response = await self.query_client.query_simple(
            payload=chat_request.model_dump(),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id
        )

        # Parsear respuesta
        response = ChatResponse.model_validate(query_response)
        
        # Actualizar conversation_id con el nuestro
        response.conversation_id = conversation_id

        # Extraer el mensaje del usuario (último mensaje con role="user")
        user_message = next(
            (msg.content for msg in reversed(chat_request.messages) if msg.role == "user"),
            "Sin mensaje"
        )

        # Guardar conversación (fire-and-forget)
        await self.conversation_client.save_conversation(
            conversation_id=conversation_id,
            message_id=message_id,
            user_message=user_message,
            agent_message=response.message.content or "",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
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