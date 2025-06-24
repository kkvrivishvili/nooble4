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
from common.models.config_models import ExecutionConfig
from common.clients.redis.redis_state_manager import RedisStateManager

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..tools.base_tool import BaseTool
from ..tools.knowledge_tool import KnowledgeTool
from ..tools.registry import ToolRegistry

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
        
        # State manager para el historial
        self.history_manager = RedisStateManager[ConversationHistory](
            redis_conn=redis_conn,
            state_model=ConversationHistory,
            app_settings=settings
        )

    async def handle_advance_chat(
        self,
        payload: Dict[str, Any],
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
            
            # Extraer execution_config para uso local
            execution_config = chat_request.execution_config
            
            # Construir key para cache
            cache_key = self._build_cache_key(tenant_id, session_id)
            
            # Recuperar historial
            history = await self.history_manager.load_state(cache_key)
            
            # Preparar conversation_id y mensajes iniciales
            if history:
                conversation_id = history.conversation_id
                
                # Integrar historial
                system_messages = [msg for msg in chat_request.messages if msg.role == "system"]
                user_messages = [msg for msg in chat_request.messages if msg.role == "user"]
                
                # Integrar mensajes con historial
                base_messages = system_messages + history.to_chat_messages() + user_messages
                
                self._logger.info(
                    f"Historial integrado para ReAct",
                    extra={
                        "conversation_id": conversation_id,
                        "historical_messages": len(history.messages)
                    }
                )
            else:
                conversation_id = str(uuid.uuid4())
                history = ConversationHistory(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    agent_id=agent_id
                )
                base_messages = chat_request.messages.copy()

            # Registrar herramientas si hay configuración RAG
            if chat_request.rag_config:
                await self._register_knowledge_tool(
                    rag_config=chat_request.rag_config,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id
                )
                
                # Agregar knowledge tool a las herramientas disponibles
                if not chat_request.tools:
                    chat_request.tools = []
                
                knowledge_tool_def = {
                    "type": "function",
                    "function": {
                        "name": "knowledge",
                        "description": "Search relevant information from the knowledge base",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
                
                if not any(t.get("function", {}).get("name") == "knowledge" for t in chat_request.tools):
                    chat_request.tools.append(knowledge_tool_def)

            # Loop ReAct usando execution_config
            iteration = 0
            max_iterations = execution_config.max_iterations
            messages = base_messages.copy()
            final_message = None
            tools_used = []
            
            while iteration < max_iterations and final_message is None:
                iteration += 1
                
                # Preparar payload limpio para query_service (sin execution_config ni conversation_id)
                query_payload = {
                    "messages": messages,
                    "query_config": chat_request.query_config,
                    "rag_config": chat_request.rag_config,
                    "tools": chat_request.tools,
                    "tool_choice": chat_request.tool_choice
                }
                
                # Llamar a Query Service
                query_response = await self.query_client.query_advance(
                    payload=query_payload,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id
                )
                
                # Parsear respuesta
                response = ChatResponse.model_validate(query_response)
                assistant_message = response.message
                messages.append(assistant_message)
                
                # Si hay tool calls, ejecutarlas con timeout de execution_config
                if assistant_message.tool_calls:
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call["function"]["name"]
                        tools_used.append(tool_name)
                        
                        # Ejecutar tool con timeout configurado
                        try:
                            tool_result = await asyncio.wait_for(
                                self._execute_tool(
                                    tool_name=tool_name,
                                    arguments=json.loads(tool_call["function"]["arguments"]),
                                    tenant_id=tenant_id,
                                    session_id=session_id,
                                    task_id=task_id
                                ),
                                timeout=execution_config.tool_timeout
                            )
                        except asyncio.TimeoutError:
                            error_msg = f"Tool '{tool_name}' execution timed out after {execution_config.tool_timeout} seconds"
                            self._logger.error(
                                f"Tool execution timeout",
                                extra={
                                    "tool_name": tool_name,
                                    "timeout_seconds": execution_config.tool_timeout,
                                    "conversation_id": conversation_id,
                                    "iteration": iteration
                                }
                            )
                            tool_result = {"error": error_msg}
                        except Exception as e:
                            self._logger.error(
                                f"Tool execution failed",
                                extra={
                                    "tool_name": tool_name,
                                    "error": str(e),
                                    "conversation_id": conversation_id,
                                    "iteration": iteration
                                }
                            )
                            tool_result = {"error": f"Tool execution failed: {str(e)}"}
                        
                        # Agregar resultado como mensaje
                        tool_message = ChatMessage(
                            role="tool",
                            content=json.dumps(tool_result),
                            tool_call_id=tool_call["id"],
                            name=tool_name
                        )
                        messages.append(tool_message)
                
                # Si no hay tool calls y hay contenido, tenemos respuesta final
                elif assistant_message.content:
                    final_message = assistant_message
                    break

            # Si no hay respuesta después del loop
            if not final_message:
                final_message = ChatMessage(
                    role="assistant",
                    content="I couldn't generate a complete response within the iteration limit."
                )

            # Extraer mensaje del usuario original
            user_message = next(
                (msg for msg in reversed(base_messages) if msg.role == "user"),
                None
            )

            # Actualizar historial y cache
            if user_message and final_message:
                # Agregar al historial
                history.add_message(user_message)
                history.add_message(final_message)
                
                # Guardar en cache usando conversation_cache_ttl de execution_config
                await self.history_manager.save_state(
                    cache_key,
                    history,
                    expiration_seconds=execution_config.conversation_cache_ttl
                )
                
                # Guardar conversación en Conversation Service (fire-and-forget)
                await self.conversation_client.save_conversation(
                    conversation_id=conversation_id,
                    message_id=str(uuid.uuid4()),
                    user_message=user_message.content,
                    agent_message=final_message.content,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    metadata={
                        "mode": "advance",
                        "collections": chat_request.rag_config.collection_ids if chat_request.rag_config else [],
                        "tools_used": tools_used,
                        "iterations": iteration
                    }
                )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Calcular uso total de tokens
            total_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            
            return ChatResponse(
                message=final_message,
                usage=total_usage,
                conversation_id=conversation_id,
                execution_time_ms=execution_time_ms,
                sources=[],
                iterations=iteration
            )

        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error en advance chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat avanzado: {str(e)}")

    def _build_cache_key(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> str:
        """Construye la key de cache siguiendo el patrón estándar."""
        prefix = "nooble4"
        environment = self.app_settings.environment
        return f"{prefix}:{environment}:agent_execution:history:{tenant_id}:{session_id}"

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