"""
Handler para chat avanzado con soporte de tools.
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError

from ..models import (
    QueryAdvancePayload,
    QueryAdvanceResponseData
)
from common.models.chat_models import (
    ChatMessage,
    TokenUsage,
    ToolCall
)
from ..clients.groq_client import GroqClient


class AdvanceHandler(BaseHandler):
    """Handler para procesamiento de chat avanzado con tools."""
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis directa
        """
        super().__init__(app_settings, direct_redis_conn)
        self._logger.info("AdvanceHandler inicializado")
    
    async def process_advance_query(
        self,
        payload: QueryAdvancePayload,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID
    ) -> QueryAdvanceResponseData:
        """Procesa una consulta avanzada con soporte de tools."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Validar payload
            self._validate_payload(payload)
            
            # Crear cliente Groq
            groq_client = GroqClient(
                api_key=self.app_settings.groq_api_key,
                timeout=payload.agent_config.max_tokens // 100
            )
            
            # Preparar mensajes para Groq
            groq_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in payload.messages
            ]
            
            # Preparar tools para Groq
            groq_tools = [tool.model_dump() for tool in payload.tools]
            
            # Llamar a Groq con tools
            response = await groq_client.client.chat.completions.create(
                messages=groq_messages,
                model=payload.agent_config.model_name,
                temperature=payload.agent_config.temperature,
                max_tokens=payload.agent_config.max_tokens,
                top_p=payload.agent_config.top_p,
                frequency_penalty=payload.agent_config.frequency_penalty,
                presence_penalty=payload.agent_config.presence_penalty,
                stop=payload.agent_config.stop_sequences,
                tools=groq_tools,
                tool_choice=payload.tool_choice
            )
            
            # Extraer respuesta
            choice = response.choices[0]
            message = choice.message
            
            # Construir mensaje de respuesta
            response_message = ChatMessage(
                role="assistant",
                content=message.content
            )
            
            # Si hay tool calls, agregarlas
            if hasattr(message, 'tool_calls') and message.tool_calls:
                response_message.tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            # Extraer uso de tokens
            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return QueryAdvanceResponseData(
                message=response_message,
                finish_reason=choice.finish_reason,
                usage=token_usage,
                query_id=query_id,
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            self._logger.error(f"Error en advance query: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando query advance: {str(e)}")
    
    def _validate_payload(self, payload: QueryAdvancePayload):
        """Valida que el payload tenga todos los campos requeridos."""
        if not payload.agent_config:
            raise AppValidationError("agent_config es requerido")
        if not payload.tools:
            raise AppValidationError("Al menos una tool es requerida")