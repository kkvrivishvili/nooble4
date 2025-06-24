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
    
    def __init__(self, app_settings, groq_client: GroqClient, direct_redis_conn=None):
        """
        Inicializa el handler recibiendo el cliente como dependencia.
        
        Args:
            app_settings: QueryServiceSettings
            groq_client: Cliente para consultas LLM en Groq
            direct_redis_conn: Conexión Redis directa
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Validar que el cliente esté presente
        if not groq_client:
            raise ValueError("groq_client es requerido para AdvanceHandler")
            
        # Asignar el cliente recibido como dependencia
        self.groq_client = groq_client
        
        self._logger.info("AdvanceHandler inicializado con inyección de cliente")
    
    async def process_advance_query(
        self,
        data: Dict[str, Any],
        query_config: "QueryConfig",  # Config explícita desde DomainAction
        rag_config: "RAGConfig",      # Config explícita desde DomainAction
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID,
        agent_id: UUID,
    ) -> ChatResponse:
        """Procesa una consulta avanzada con soporte de tools."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Extraer datos limpios del payload (sin configuraciones)
            raw_messages = data.get("messages", [])
            tools = data.get("tools", [])
            tool_choice = data.get("tool_choice", "auto")
            
            # rag_config es ignorado en advance mode - el RAG se maneja a través de herramientas específicas
            
            # Validar datos requeridos
            if not raw_messages:
                raise AppValidationError("messages es requerido")
            if not query_config:
                raise AppValidationError("query_config es requerido")
            if not tools:
                raise AppValidationError("Al menos una tool es requerida para chat avanzado")
            
            # Validaciones específicas de Query Service para query_config
            self._validate_query_config(query_config)
            
            # Validaciones específicas de Query Service para tools
            self._validate_tools(tools)
            
            # Convertir raw messages a ChatMessage objects
            messages = []
            for msg_data in raw_messages:
                if isinstance(msg_data, dict):
                    messages.append(ChatMessage.model_validate(msg_data))
                else:
                    messages.append(msg_data)  # Ya es ChatMessage
            
            self._logger.info(
                f"Procesando chat avanzado",
                extra={
                    "tenant_id": str(tenant_id),
                    "session_id": str(session_id),
                    "query_id": query_id,
                    "tools_count": len(tools),
                    "agent_id": str(agent_id)
                }
            )
            
            # CONSTRUCCIÓN DEL SYSTEM PROMPT desde query_config
            # Si ya hay un system message, lo actualizamos. Si no, lo creamos
            system_prompt = query_config.system_prompt_template
            
            # Verificar si ya existe un system message
            has_system_msg = any(msg.role == "system" for msg in messages)
            if not has_system_msg:
                # Agregar system prompt al inicio
                system_msg = ChatMessage(role="system", content=system_prompt)
                messages.insert(0, system_msg)
            else:
                # Actualizar el primer system message encontrado
                for msg in messages:
                    if msg.role == "system":
                        msg.content = system_prompt
                        break
            
            # LLAMADA A GROQ: Formatear payload según especificaciones oficiales del SDK
            # En modo avanzado: tools y tool_choice son parámetros de nivel superior
            groq_payload = {
                "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
                "model": query_config.model.value,  # Usar el enum ChatModel
                "temperature": query_config.temperature,
                "max_tokens": query_config.max_tokens,
                "top_p": query_config.top_p,
                "frequency_penalty": query_config.frequency_penalty,
                "presence_penalty": query_config.presence_penalty,
                "stop": query_config.stop if query_config.stop else None,
                "tools": tools,  # Parámetro de nivel superior según especificaciones de Groq
                "tool_choice": tool_choice  # Parámetro de nivel superior según especificaciones de Groq
            }
            
            # Aplicar configuración dinámica del timeout si está especificada en query_config
            # Si no hay configuración específica, usar el cliente ya inyectado
            groq_client_instance = self.groq_client
            
            # Si hay configuración específica en query_config (timeout o max_retries), usar with_options
            if query_config.timeout is not None or query_config.max_retries is not None:
                options = {}
                if query_config.timeout is not None:
                    options["timeout"] = query_config.timeout
                if query_config.max_retries is not None:
                    options["max_retries"] = query_config.max_retries
                
                # Crear una copia del cliente con las opciones específicas
                groq_client_instance = self.groq_client.with_options(**options)
            
            # Llamar al cliente de Groq (original o con opciones específicas)
            response_text, token_usage = await groq_client_instance.generate(**groq_payload)
            
            # Construir respuesta
            end_time = time.time()
            
            # Crear mensaje de respuesta
            response_message = ChatMessage(
                role="assistant",
                content=response_text
            )
            
            response = ChatResponse(
                conversation_id=UUID(query_id),
                message=response_message,
                usage=token_usage,
                sources=[],  # En advance mode no hay sources directos de RAG
                execution_time_ms=int((end_time - start_time) * 1000)
            )
            
            self._logger.info(
                f"Chat avanzado procesado exitosamente. Tokens: {token_usage.total_tokens}",
                extra={
                    "query_id": query_id,
                    "processing_time": response.execution_time_ms,
                    "tools_used": len(tools)
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error procesando chat avanzado: {str(e)}", exc_info=True)
            if isinstance(e, (AppValidationError, ExternalServiceError)):
                raise
            raise ExternalServiceError(f"Error interno en chat avanzado: {str(e)}")
    
    def _validate_query_config(self, query_config):
        """Valida la configuración de query."""
        from common.models.config_models import QueryConfig
        
        # Validar campos requeridos
        if not query_config.model:
            raise AppValidationError("Modelo de lenguaje es requerido")
        if not query_config.system_prompt_template:
            raise AppValidationError("Plantilla de prompt del sistema es requerida")
        if query_config.temperature is None:
            raise AppValidationError("Temperatura es requerida")
        if not query_config.max_tokens:
            raise AppValidationError("Cantidad máxima de tokens es requerida")
        if query_config.top_p is None:
            raise AppValidationError("Umbral de probabilidad es requerido")
        if query_config.frequency_penalty is None:
            raise AppValidationError("Penalización de frecuencia es requerida")
        if query_config.presence_penalty is None:
            raise AppValidationError("Penalización de presencia es requerida")
        
        # Validar valores válidos
        if query_config.temperature < 0 or query_config.temperature > 1:
            raise AppValidationError("Temperatura debe estar entre 0 y 1")
        if query_config.max_tokens < 1:
            raise AppValidationError("Cantidad máxima de tokens debe ser mayor que 0")
        if query_config.top_p < 0 or query_config.top_p > 1:
            raise AppValidationError("Umbral de probabilidad debe estar entre 0 y 1")
        if query_config.frequency_penalty < 0 or query_config.frequency_penalty > 1:
            raise AppValidationError("Penalización de frecuencia debe estar entre 0 y 1")
        if query_config.presence_penalty < 0 or query_config.presence_penalty > 1:
            raise AppValidationError("Penalización de presencia debe estar entre 0 y 1")
    
    def _validate_tools(self, tools):
        """Valida la configuración de herramientas."""
        if not isinstance(tools, list):
            raise AppValidationError("Tools debe ser una lista")
        
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                raise AppValidationError(f"Tool {i} debe ser un diccionario")
            
            # Validar estructura básica según especificaciones de Groq
            if tool.get("type") != "function":
                raise AppValidationError(f"Tool {i}: type debe ser 'function'")
            
            function_def = tool.get("function")
            if not function_def:
                raise AppValidationError(f"Tool {i}: 'function' es requerida")
            
            if not isinstance(function_def, dict):
                raise AppValidationError(f"Tool {i}: 'function' debe ser un diccionario")
            
            if not function_def.get("name"):
                raise AppValidationError(f"Tool {i}: 'name' es requerida en function")
            
            if not function_def.get("description"):
                raise AppValidationError(f"Tool {i}: 'description' es requerida en function")
            
            # Validar parameters si existe
            parameters = function_def.get("parameters")
            if parameters and not isinstance(parameters, dict):
                raise AppValidationError(f"Tool {i}: 'parameters' debe ser un diccionario")
            
            if parameters:
                if parameters.get("type") != "object":
                    raise AppValidationError(f"Tool {i}: parameters.type debe ser 'object'")
                
                properties = parameters.get("properties")
                if properties and not isinstance(properties, dict):
                    raise AppValidationError(f"Tool {i}: parameters.properties debe ser un diccionario")