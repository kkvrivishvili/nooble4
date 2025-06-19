"""
Handler para chat avanzado con capacidades ReAct.
"""
import logging
import time
import uuid
import json
from typing import Dict, Any, List, Optional

from common.handlers.base_handler import BaseHandler
from common.errors.exceptions import ExternalServiceError, ToolExecutionError
from common.models.chat_models import (
    AdvanceChatPayload,
    ChatMessage,
    QueryAdvancePayload,
    QueryRAGPayload,
    ToolDefinition
)

from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..models.execution_responses import AdvanceExecutionResponse
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
        settings: ExecutionServiceSettings
    ):
        super().__init__(settings)
        self.query_client = query_client
        self.conversation_client = conversation_client
        self.tool_registry = tool_registry
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle_advance_chat(
        self,
        payload: AdvanceChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> AdvanceExecutionResponse:
        """
        Ejecuta chat avanzado con loop ReAct.
        """
        start_time = time.time()
        conversation_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        thinking_steps = []
        tools_used = []
        
        try:
            self._logger.info(
                f"Procesando chat avanzado con ReAct",
                extra={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "tools_count": len(payload.tools)
                }
            )

            # Registrar herramientas disponibles
            await self._register_tools(payload, tenant_id, session_id, task_id)

            # Construir mensajes iniciales con system prompt
            messages = [
                ChatMessage(role="system", content=payload.system_prompt)
            ]
            
            # Agregar historial
            messages.extend(payload.conversation_history)
            
            # Agregar mensaje del usuario
            messages.append(ChatMessage(role="user", content=payload.user_message))

            # Preparar tools para Query Service (agregar knowledge tool)
            all_tools = list(payload.tools)
            if self.tool_registry.get("knowledge"):
                knowledge_tool_def = ToolDefinition(
                    type="function",
                    function={
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
                )
                all_tools.append(knowledge_tool_def)

            # Loop ReAct
            iteration = 0
            final_answer = None
            
            while iteration < payload.max_iterations and final_answer is None:
                iteration += 1
                thinking_steps.append(f"Iteration {iteration}: Processing...")
                
                # 1. Llamar a Query Service
                query_payload = QueryAdvancePayload(
                    messages=messages,
                    agent_config=payload.agent_config,
                    tools=all_tools,
                    tool_choice=payload.tool_choice
                )
                
                query_response = await self.query_client.query_advance(
                    payload=query_payload.model_dump(),
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id
                )
                
                # 2. Procesar respuesta
                assistant_message = ChatMessage.model_validate(query_response["message"])
                messages.append(assistant_message)
                
                # 3. Si hay tool calls, ejecutarlas
                if assistant_message.tool_calls:
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call["function"]["name"]
                        tools_used.append(tool_name)
                        
                        # Ejecutar tool
                        tool_result = await self._execute_tool(
                            tool_name=tool_name,
                            arguments=json.loads(tool_call["function"]["arguments"]),
                            tenant_id=tenant_id,
                            session_id=session_id,
                            task_id=task_id
                        )
                        
                        # Agregar resultado como mensaje
                        tool_message = ChatMessage(
                            role="tool",
                            content=json.dumps(tool_result),
                            tool_call_id=tool_call["id"]
                        )
                        messages.append(tool_message)
                        
                        thinking_steps.append(f"Used tool '{tool_name}': {tool_result.get('summary', 'OK')}")
                
                # 4. Si no hay tool calls, tenemos respuesta final
                elif assistant_message.content:
                    final_answer = assistant_message.content
                    break

            # Si no hay respuesta después del loop
            if not final_answer:
                final_answer = "I couldn't generate a complete response within the iteration limit."

            # Guardar conversación
            await self.conversation_client.save_conversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_message=payload.user_message,
                agent_message=final_answer,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                metadata={
                    "mode": "advance",
                    "collections": payload.collection_ids,
                    "tools_used": tools_used,
                    "iterations": iteration,
                    "thinking_steps": thinking_steps
                }
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AdvanceExecutionResponse(
                message=final_answer,
                thinking=thinking_steps,
                tools_used=tools_used,
                conversation_id=conversation_id,
                execution_time_ms=execution_time_ms,
                iterations=iteration
            )

        except ExternalServiceError:
            raise
        except Exception as e:
            self._logger.error(f"Error en advance chat handler: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando chat avanzado: {str(e)}")

    async def _register_tools(
        self, 
        payload: AdvanceChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> None:
        """Registra las herramientas disponibles."""
        # Limpiar registro previo
        self.tool_registry.clear()
        
        # Registrar knowledge tool
        knowledge_tool = KnowledgeTool(
            query_client=self.query_client,
            collection_ids=payload.collection_ids,
            document_ids=payload.document_ids,
            embedding_config=payload.embedding_config,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id
        )
        self.tool_registry.register(knowledge_tool)

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tenant_id: str,
        session_id: str,
        task_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Ejecuta una herramienta y retorna el resultado."""
        tool = self.tool_registry.get(tool_name)
        
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "summary": "Tool not available"
            }
        
        try:
            if tool_name == "knowledge":
                # Para knowledge tool, hacer búsqueda RAG
                rag_payload = QueryRAGPayload(
                    query_text=arguments.get("query", ""),
                    collection_ids=tool.collection_ids,
                    document_ids=tool.document_ids,
                    embedding_config=tool.embedding_config,
                    top_k=arguments.get("top_k", 5),
                    similarity_threshold=arguments.get("similarity_threshold", 0.7)
                )
                
                response = await self.query_client.query_rag(
                    payload=rag_payload.model_dump(),
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id
                )
                
                # Formatear respuesta
                chunks = response.get("chunks", [])
                if chunks:
                    formatted_chunks = "\n\n".join([
                        f"[Source: {c['source']}, Score: {c['score']:.2f}]\n{c['content']}"
                        for c in chunks[:3]  # Top 3
                    ])
                    return {
                        "found": len(chunks),
                        "content": formatted_chunks,
                        "summary": f"Found {len(chunks)} relevant results"
                    }
                else:
                    return {
                        "found": 0,
                        "content": "No relevant information found",
                        "summary": "No results"
                    }
            else:
                # Otras tools custom
                result = await tool.execute(**arguments)
                return {
                    "result": result,
                    "summary": f"Tool '{tool_name}' executed successfully"
                }
                
        except Exception as e:
            self._logger.error(f"Error executing tool '{tool_name}': {e}")
            return {
                "error": str(e),
                "summary": f"Tool '{tool_name}' failed"
            }