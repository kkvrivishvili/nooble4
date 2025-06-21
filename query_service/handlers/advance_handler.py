"""
Handler para chat avanzado con soporte de tools.
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError
from common.models.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    TokenUsage
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
        payload: ChatRequest,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID
    ) -> ChatResponse:
        """Procesa una consulta avanzada con soporte de tools."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Validar que tenga tools (requerido para advance)
            if not payload.tools:
                raise AppValidationError("Al menos una tool es requerida para chat avanzado")
            
            self._logger.info(
                f"Procesando chat avanzado",
                extra={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "query_id": query_id,
                    "tools_count": len(payload.tools)
                }
            )
            
            # Crear cliente Groq
            groq_client = GroqClient(
                api_key=self.app_settings.groq_api_key,
                timeout=max(60, payload.max_tokens // 100)  # Timeout dinámico
            )
            
            # Preparar mensajes para Groq
            groq_messages = [
                self._message_to_groq_format(msg)
                for msg in payload.messages
            ]
            
            # Llamar a Groq con tools
            response = await groq_client.client.chat.completions.create(
                messages=groq_messages,
                model=payload.model.value,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                top_p=payload.top_p,
                frequency_penalty=payload.frequency_penalty,
                presence_penalty=payload.presence_penalty,
                stop=payload.stop,
                tools=payload.tools,  # Ya están en formato Groq
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
            
            return ChatResponse(
                message=response_message,
                usage=token_usage,
                conversation_id=query_id,
                execution_time_ms=execution_time_ms,
                sources=[]  # No hay sources en advance (las herramientas manejan sus propias fuentes)
            )
            
        except Exception as e:
            self._logger.error(f"Error en advance query: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando query advance: {str(e)}")
    
    def _message_to_groq_format(self, msg: ChatMessage) -> Dict[str, Any]:
        """Convierte un ChatMessage al formato esperado por Groq."""
        groq_msg = {"role": msg.role}
        
        if msg.content:
            groq_msg["content"] = msg.content
        
        if msg.tool_calls:
            groq_msg["tool_calls"] = msg.tool_calls
        
        if msg.tool_call_id:
            groq_msg["tool_call_id"] = msg.tool_call_id
        
        if msg.name:
            groq_msg["name"] = msg.name
        
        return groq_msg