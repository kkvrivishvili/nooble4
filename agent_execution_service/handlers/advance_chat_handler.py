"""
Handler para chat avanzado con capacidades ReAct.
"""
import logging
import time
import uuid
import json
from typing import Dict, Any, List, Optional
import asyncio

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    TokenUsage,
    ConversationHistory
)
from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig
from common.clients.redis.cache_manager import CacheManager

from common.config.service_settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..tools.base_tool import BaseTool
from ..tools.knowledge_tool import KnowledgeTool
from ..tools.registry import ToolRegistry
from .conversation_handler import ConversationHelper


logger = logging.getLogger(__name__)


class AdvanceChatHandler(BaseHandler):
    """Handler para modo avanzado: ReAct con herramientas."""

    def __init__(
        self,
        query_client: QueryClient,
        conversation_client: ConversationClient,
        tool_registry: ToolRegistry,
        settings: ExecutionServiceSettings,
        redis_conn
    ):
        super().__init__(settings)
        self.query_client = query_client
        self.conversation_client = conversation_client
        self.tool_registry = tool_registry
        self.redis_conn = redis_conn
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Cache manager para el historial
        self.history_manager = CacheManager[ConversationHistory](
            redis_conn=redis_conn,
            state_model=ConversationHistory,
            app_settings=settings,
            default_ttl=None  # El TTL se especifica en cada operación de guardado
        )
        
        self.conversation_helper = ConversationHelper(
            cache_manager=self.history_manager,
            conversation_client=self.conversation_client
        )

    async def handle_advance_chat(
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
        Ejecuta chat avanzado con loop ReAct.
        Maneja cache de historial localmente.
        """
        start_time = time.time()
        
        try:
            # Parsear ChatRequest
            chat_request = ChatRequest.model_validate(payload)
            
            # Delegar a ConversationHelper
            chat_response = await self.conversation_helper.process_chat(
                chat_request=chat_request,
                execution_config=execution_config,
                query_config=query_config,
                rag_config=rag_config,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                agent_id=agent_id
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Calcular uso total de tokens
            total_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            
            return ChatResponse(
                message=chat_response.message,
                usage=total_usage,
                conversation_id=chat_response.conversation_id,
                execution_time_ms=execution_time_ms,
                sources=[],
                iterations=chat_response.iterations
            )

        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error en advance chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat avanzado: {str(e)}")

    async def _register_knowledge_tool(
        self, 
        rag_config: RAGConfig,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID,
        agent_id: uuid.UUID
    ) -> None:
        """Registra la herramienta de conocimiento si hay configuración RAG."""
        self.tool_registry.clear()
        
        knowledge_tool = KnowledgeTool(
            query_client=self.query_client,
            rag_config=rag_config,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id
        )
        self.tool_registry.register(knowledge_tool)

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        task_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Ejecuta una herramienta y retorna el resultado."""
        tool = self.tool_registry.get(tool_name)
        
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tool_registry.get_all().keys())
            }
        
        try:
            result = await tool.execute(**arguments)
            return result
                
        except Exception as e:
            self._logger.error(f"Error ejecutando tool {tool_name}: {e}", exc_info=True)
            return {
                "error": f"Tool execution failed: {str(e)}",
                "tool_name": tool_name
            }