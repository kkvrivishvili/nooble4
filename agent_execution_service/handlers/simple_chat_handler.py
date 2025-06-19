"""
Handler para chat simple con RAG.
"""
import logging
import time
import uuid
from typing import Dict, Any, Optional
from common.handlers.base_handler import BaseHandler
from ..config.settings import ExecutionServiceSettings
from common.errors.exceptions import ExternalServiceError

from ..clients.query_client import QueryClient
from ..models.payloads import ExecuteSimpleChatPayload, ExecuteSimpleChatResponse
from query_service.models import QueryServiceChatMessage # For constructing messages for llm_direct

logger = logging.getLogger(__name__)

class SimpleChatHandler(BaseHandler):
    """Handler para modo simple: Chat + RAG."""

    def __init__(self, query_client: QueryClient, settings: ExecutionServiceSettings):
        super().__init__(settings) # BaseHandler espera CommonAppSettings, ExecutionServiceSettings hereda de ella
        self.query_client = query_client
        self.settings = settings 

    async def execute_simple_chat(
        self,
        payload: ExecuteSimpleChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> ExecuteSimpleChatResponse:
        """
        Ejecuta chat simple con o sin RAG, delegando siempre al Query Service.
        """
        start_time = time.time()
        
        try:
            self._logger.info(
                f"Iniciando chat simple para tenant {tenant_id}, session {session_id}"
            )

            if payload.use_rag:
                # Delegar al Query Service para RAG
                self._logger.debug("Usando RAG - delegando al Query Service")
                
                result = await self.query_client.query_with_rag(
                    query_text=payload.user_message,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    collection_ids=payload.collection_ids,
                    llm_config_params=payload.llm_config.model_dump(exclude_none=True) if payload.llm_config else None,
                    conversation_history=payload.conversation_history # Pass conversation history
                )
                
                response_text = result.response or ""
                # ExecuteSimpleChatResponse expects List[Dict[str, Any]] for sources_used
                sources = [src.model_dump() for src in result.search_results] if result.search_results else []
                context = result.rag_context_used or ""
                tokens_used = result.token_usage.total_tokens if result.token_usage else None 
                
            else:
                # Chat directo sin RAG - TAMBIÉN delegando al Query Service
                self._logger.debug("Chat directo sin RAG - delegando al Query Service")
                
                # Construir mensajes para LLM directo
                llm_messages: List[QueryServiceChatMessage] = []
                if payload.system_prompt:
                    llm_messages.append(QueryServiceChatMessage(role="system", content=payload.system_prompt))
                
                # payload.conversation_history is already List[QueryServiceChatMessage]
                llm_messages.extend(payload.conversation_history)
                
                llm_messages.append(QueryServiceChatMessage(role="user", content=payload.user_message))
                
                # Llamar Query Service para LLM directo
                result = await self.query_client.llm_direct(
                    messages=llm_messages, # Pass List[QueryServiceChatMessage]
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    llm_config_params=payload.llm_config.model_dump(exclude_none=True) if payload.llm_config else None
                )
                
                response_text = result.response or ""
                sources = [] 
                context = None 
                tokens_used = result.token_usage.total_tokens if result.token_usage else None 

            execution_time = time.time() - start_time

            self._logger.info(
                f"Chat simple completado en {execution_time:.2f}s, "
                f"tokens: {tokens_used or 'N/A'}"
            )

            return ExecuteSimpleChatResponse(
                response=response_text,
                sources_used=sources,
                rag_context=context,
                execution_time_seconds=execution_time,
                tokens_used=tokens_used 
            )

        except ExternalServiceError:
            # Re-lanzar errores de servicios externos sin modificar
            raise
        except Exception as e:
            self._logger.error(f"Error en chat simple: {e}", exc_info=True) 
            raise ExternalServiceError(
                f"Error interno en chat simple: {str(e)}",
                original_exception=e
            )

    async def cleanup(self):
        """Limpia recursos del handler."""
        try:
            if hasattr(self.query_client, 'close') and callable(getattr(self.query_client, 'close')):
                await self.query_client.close()
                
            self._logger.debug("SimpleChatHandler limpiado correctamente")
        except Exception as e:
            self._logger.error(f"Error limpiando SimpleChatHandler: {e}", exc_info=True) 