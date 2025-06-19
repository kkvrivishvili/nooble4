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
from ..config.settings import ExecutionServiceSettings
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from ..models.execution_payloads import AdvanceChatPayload
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
        
        TODO: Implementar lógica completa de ReAct
        Por ahora solo estructura base.
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

            # Construir mensajes iniciales
            messages = self._build_initial_messages(payload)

            # TODO: Implementar loop ReAct
            # Por ahora, placeholder con una sola iteración
            iteration = 0
            final_answer = None
            
            while iteration < payload.max_iterations and final_answer is None:
                iteration += 1
                
                # 1. Llamar a Query Service para obtener respuesta con posibles tool_calls
                # query_response = await self.query_client.query_advance(...)
                
                # 2. Si hay tool_calls, ejecutarlas
                # for tool_call in tool_calls:
                #     if tool_call.name == "knowledge":
                #         result = await self._execute_knowledge_tool(...)
                #     else:
                #         result = await self._execute_custom_tool(...)
                
                # 3. Agregar resultados a messages
                # 4. Determinar si tenemos respuesta final
                
                # Placeholder temporal
                thinking_steps.append(f"Iteración {iteration}: Analizando la pregunta...")
                thinking_steps.append("Determinando herramientas necesarias...")
                
                # Por ahora, respuesta directa sin tools
                final_answer = f"[MODO ADVANCE - NO IMPLEMENTADO] Respuesta placeholder para: {payload.user_message}"
                break

            # Guardar conversación
            await self.conversation_client.save_conversation(
                conversation_id=conversation_id,
                message_id=message_id,
                user_message=payload.user_message,
                agent_message=final_answer or "No se pudo generar respuesta",
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                metadata={
                    "mode": "advance",
                    "collections": payload.collection_ids,
                    "tools_used": tools_used,
                    "iterations": iteration
                }
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return AdvanceExecutionResponse(
                message=final_answer or "No se pudo generar respuesta",
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
        
        # Registrar knowledge tool (siempre disponible)
        knowledge_tool = KnowledgeTool(
            query_client=self.query_client,
            collection_ids=payload.collection_ids,
            document_ids=payload.document_ids,
            embedding_config=payload.embedding_config.model_dump(),
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id
        )
        self.tool_registry.register(knowledge_tool)
        
        # TODO: Registrar otras herramientas custom basadas en payload.tools
        for tool_def in payload.tools:
            if tool_def.name != "knowledge":  # Knowledge ya está registrada
                # TODO: Crear instancia de tool custom basada en tool_def
                self._logger.debug(f"Tool custom '{tool_def.name}' pendiente de implementación")

    def _build_initial_messages(self, payload: AdvanceChatPayload) -> List[Dict[str, str]]:
        """Construye los mensajes iniciales para el LLM."""
        messages = []
        
        # System message con instrucciones ReAct
        system_message = """You are a helpful AI assistant with access to tools.
When you need to use a tool, you will receive the results and can continue reasoning.
Think step by step and use tools when necessary to answer the user's question accurately."""
        
        messages.append({"role": "system", "content": system_message})
        
        # Agregar historial si existe
        if payload.conversation_history:
            messages.extend(payload.conversation_history)
        
        # Agregar mensaje del usuario
        messages.append({"role": "user", "content": payload.user_message})
        
        return messages

    async def _execute_knowledge_tool(
        self,
        query: str,
        tool: KnowledgeTool
    ) -> str:
        """Ejecuta la herramienta de conocimiento."""
        try:
            result = await tool.execute(query=query)
            return json.dumps(result)
        except Exception as e:
            self._logger.error(f"Error ejecutando knowledge tool: {e}")
            return f"Error: {str(e)}"

    async def _execute_custom_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """Ejecuta una herramienta custom."""
        # TODO: Implementar ejecución de tools custom
        return f"Resultado de {tool_name}: No implementado"