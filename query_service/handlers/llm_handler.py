"""
Handler para llamadas directas al LLM sin RAG.

Este handler maneja consultas directas al LLM, incluyendo soporte para
tool calling y conversaciones sin contexto de búsqueda vectorial.
"""

import logging
import time
import json
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4 # Ensure uuid4 is available if used, or just UUID if str(UUID()) is intended

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models import (
    QueryLLMDirectPayload, # Added
    LLMDirectResponseData,
    QueryServiceToolCall,
    QueryServiceChatMessage,
    QueryServiceToolDefinition
)
from ..models.base_models import TokenUsage # Added
from ..clients.groq_client import GroqClient


class LLMHandler(BaseHandler):
    """
    Handler para procesamiento directo de LLM sin RAG.
    
    Maneja llamadas directas al LLM con soporte para tool calling,
    ideal para conversaciones simples o agentes que necesitan
    capacidades de función.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        self.groq_client = GroqClient(
            api_key=app_settings.groq_api_key,
            timeout=app_settings.llm_timeout_seconds,
            max_retries=app_settings.groq_max_retries
        )
        
        self.default_llm_model = app_settings.default_llm_model
        self.llm_temperature = app_settings.llm_temperature
        self.llm_max_tokens = app_settings.llm_max_tokens
        self.llm_top_p = app_settings.llm_top_p
        self.llm_frequency_penalty = app_settings.llm_frequency_penalty
        self.llm_presence_penalty = app_settings.llm_presence_penalty
        self.available_models = app_settings.available_llm_models
        
        self._logger.info("LLMHandler inicializado")
    
    async def process_llm_direct(
        self,
        payload: QueryLLMDirectPayload,
        tenant_id: str, # Retained for logging/operational context
        session_id: str, # Retained for logging/operational context
        # user_id: Optional[str] = None, # Not directly used, can be in payload.llm_config.user if needed by LLM provider
        trace_id: Optional[UUID] = None, # Retained for operational context
        correlation_id: Optional[UUID] = None # Used for query_id
    ) -> LLMDirectResponseData:
        """
        Procesa una consulta directa al LLM utilizando QueryLLMDirectPayload.
        """
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())

        # Extract parameters from payload
        messages = payload.messages
        tools = payload.tools
        tool_choice = payload.tool_choice
        
        # Effective LLM parameters from payload.llm_config or handler defaults
        qs_llm_config = payload.llm_config
        llm_model_eff = qs_llm_config.model_name if qs_llm_config.model_name else self.default_llm_model
        temperature_eff = qs_llm_config.temperature if qs_llm_config.temperature is not None else self.llm_temperature
        max_tokens_eff = qs_llm_config.max_tokens if qs_llm_config.max_tokens is not None else self.llm_max_tokens
        top_p_eff = qs_llm_config.top_p if qs_llm_config.top_p is not None else self.llm_top_p
        frequency_penalty_eff = qs_llm_config.frequency_penalty if qs_llm_config.frequency_penalty is not None else self.llm_frequency_penalty
        presence_penalty_eff = qs_llm_config.presence_penalty if qs_llm_config.presence_penalty is not None else self.llm_presence_penalty
        stop_sequences_eff = qs_llm_config.stop_sequences # Can be None
        # user_eff = qs_llm_config.user # If Groq client supports user field

        self._logger.info(
            f"Procesando LLM directo: {len(messages)} mensajes",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "task_id": str(payload.task_id) if hasattr(payload, 'task_id') and payload.task_id else None, # Assuming task_id might be part of payload
                "model": llm_model_eff,
                "has_tools": bool(tools)
            }
        )
        
        try:
            response_content_str, token_usage_dict, finish_reason_str, tool_calls_raw_data = await self._generate_llm_response(
                messages=messages,
                model=llm_model_eff,
                temperature=temperature_eff,
                max_tokens=max_tokens_eff,
                top_p=top_p_eff,
                frequency_penalty=frequency_penalty_eff,
                presence_penalty=presence_penalty_eff,
                stop_sequences=stop_sequences_eff,
                tools=tools,
                tool_choice=tool_choice
                # user=user_eff # Pass if Groq client supports it
            )
            
            processed_tool_calls_for_message = None
            if tool_calls_raw_data:
                processed_tool_calls_for_message = [
                    QueryServiceToolCall(
                        id=tc_raw.get("id", ""), 
                        type=tc_raw.get("type", "function"),
                        function=tc_raw.get("function", {}) # Validated by QueryServiceToolCall
                    )
                    for tc_raw in tool_calls_raw_data
                ]
            
            # Create the assistant's message for the response
            assistant_response_message = QueryServiceChatMessage(
                role="assistant",
                content=response_content_str,
                tool_calls=processed_tool_calls_for_message
            )

            token_usage_for_response = TokenUsage(
                prompt_tokens=token_usage_dict.get("prompt_tokens", 0),
                completion_tokens=token_usage_dict.get("completion_tokens", 0),
                total_tokens=token_usage_dict.get("total_tokens", 0)
            )
            
            llm_info_for_response = {"model_name": llm_model_eff, "provider": "groq"} # Example
            generation_time_ms = int((time.time() - start_time) * 1000)
            
            response = LLMDirectResponseData(
                query_id=query_id,
                message=assistant_response_message,
                usage=token_usage_for_response,
                finish_reason=finish_reason_str,
                llm_model_info=llm_info_for_response,
                generation_time_ms=generation_time_ms,
                metadata={
                    "temperature_used": temperature_eff,
                    "max_tokens_used": max_tokens_eff,
                    "tool_choice_used": tool_choice,
                    "has_tools_provided": bool(tools)
                }
                # timestamp is default_factory
            )
            
            self._logger.info(
                f"LLM directo completado en {generation_time_ms}ms",
                extra={
                    "query_id": query_id,
                    "tokens": token_usage.get("total_tokens"),
                    "finish_reason": finish_reason,
                    "has_tool_calls": bool(processed_tool_calls)
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error en LLM directo: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error procesando LLM directo: {str(e)}",
                original_exception=e
            )
    
    async def _generate_llm_response(
        self,
        messages: List[QueryServiceChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        frequency_penalty: float,
        presence_penalty: float,
        stop_sequences: Optional[List[str]],
        tools: Optional[List[QueryServiceToolDefinition]],
        tool_choice: Optional[str]
    ) -> Tuple[str, Dict[str, int], str, Optional[List[Dict[str, Any]]]]: # Adjusted tool_calls_data type hint for clarity
        """
        Genera respuesta usando el cliente Groq.
        """
        try:
            if model not in self.available_models:
                self._logger.warning(f"Modelo {model} no disponible, usando default: {self.default_llm_model}")
                model = self.default_llm_model
            
            # Transform messages and tools for Groq client
            groq_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
            groq_tools = [tool.model_dump() for tool in tools] if tools else None

            groq_params = {
                "model": model,
                "messages": groq_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty
            }
            
            if stop_sequences:
                groq_params["stop"] = stop_sequences
            
            if groq_tools:
                groq_params["tools"] = groq_tools
                if tool_choice:
                    groq_params["tool_choice"] = tool_choice
            
            api_response = await self.groq_client.client.chat.completions.create(**groq_params)
            
            choice = api_response.choices[0]
            message = choice.message
            
            content = message.content or ""
            finish_reason = choice.finish_reason
            
            response_tool_calls = None
            if hasattr(message, 'tool_calls') and message.tool_calls:
                response_tool_calls = [
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
            
            token_usage = {}
            if api_response.usage:
                token_usage = {
                    "prompt_tokens": api_response.usage.prompt_tokens,
                    "completion_tokens": api_response.usage.completion_tokens,
                    "total_tokens": api_response.usage.total_tokens
                }
            
            return content, token_usage, finish_reason, response_tool_calls
            
        except Exception as e:
            self._logger.error(f"Error generando respuesta LLM con {model}: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error al generar respuesta con {model}: {str(e)}",
                original_exception=e
            )
    
    async def cleanup(self):
        """Limpia recursos del handler."""
        try:
            if hasattr(self.groq_client, 'close') and callable(getattr(self.groq_client, 'close')):
                await self.groq_client.close()
            self._logger.debug("LLMHandler limpiado correctamente")
        except Exception as e:
            self._logger.error(f"Error limpiando LLMHandler: {e}", exc_info=True)
