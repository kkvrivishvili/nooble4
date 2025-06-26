"""
Handler para procesamiento avanzado de chat con herramientas y ReAct loops.

Maneja conversaciones complejas con tool calls y múltiples iteraciones.
Delega la gestión de conversaciones al ConversationHelper.
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List

from common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, ConversationHistory
from common.clients.redis import CacheManager
from ..clients.query_client import QueryClient
from ..clients.conversation_client import ConversationClient
from .conversation_handler import ConversationHelper


logger = logging.getLogger(__name__)


class AdvanceChatHandler:
    """
    Handler para procesamiento avanzado de chat con herramientas.
    
    Maneja conversaciones con ReAct loops, tool calls y múltiples iteraciones,
    usando ConversationHelper para gestión de historial.
    """
    
    def __init__(
        self,
        query_client: QueryClient,
        conversation_client: ConversationClient,
        cache_manager: CacheManager,
        action
    ):
        """
        Inicializa AdvanceChatHandler.
        
        Args:
            query_client: Cliente para consultas al LLM
            conversation_client: Cliente para persistencia de conversaciones
            cache_manager: Gestor de cache
            action: DomainAction que contiene la configuración en action.execution_config
        """
        self.query_client = query_client
        self.cache_manager = cache_manager
        self.action = action
        
        # Inicializar ConversationHelper
        self.conversation_helper = ConversationHelper(
            cache_manager=cache_manager,
            conversation_client=conversation_client
        )
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def process_chat(self, chat_request: ChatRequest) -> ChatResponse:
        """
        Procesa una solicitud de chat avanzado con herramientas.
        
        Args:
            chat_request: Solicitud de chat con mensajes y metadatos
            
        Returns:
            Respuesta del chat después del loop ReAct
        """
        start_time = time.time()
        
        try:            
            self.logger.info(
                "Iniciando procesamiento de chat avanzado",
                extra={
                    "tenant_id": str(chat_request.tenant_id),
                    "session_id": str(chat_request.session_id),
                    "agent_id": str(chat_request.agent_id),
                    "task_id": str(chat_request.task_id),
                    "messages_count": len(chat_request.messages)
                }
            )
            
            # 1. Obtener o crear conversación
            history = await self.conversation_helper.get_or_create_conversation(
                tenant_id=chat_request.tenant_id,
                session_id=chat_request.session_id,
                agent_id=chat_request.agent_id
            )
            
            # 2. Separar mensajes por tipo
            system_messages = [msg for msg in chat_request.messages if msg.role == "system"]
            user_messages = [msg for msg in chat_request.messages if msg.role == "user"]
            
            # 3. Integrar historial con mensajes nuevos
            integrated_messages = self.conversation_helper.integrate_history_with_messages(
                history=history,
                system_messages=system_messages,
                user_messages=user_messages
            )
            
            # 4. Ejecutar loop ReAct con herramientas
            final_response, iterations_metadata = await self._execute_react_loop(
                messages=integrated_messages,
                chat_request=chat_request
            )
            
            # 5. Crear respuesta final
            response_message = ChatMessage(
                role="assistant",
                content=final_response["content"]
            )
            
            execution_time = time.time() - start_time
            
            chat_response = ChatResponse(
                message=response_message,
                conversation_id=history.conversation_id,
                metadata={
                    "mode": "advance",
                    "execution_time_seconds": round(execution_time, 2),
                    "react_iterations": len(iterations_metadata),
                    "total_messages": len(integrated_messages),
                    **iterations_metadata,
                    **chat_request.metadata
                }
            )
            
            # 6. Extraer último mensaje de usuario para guardar
            last_user_message = user_messages[-1] if user_messages else ChatMessage(
                role="user", 
                content="[Sin mensaje de usuario]"
            )
            
            # 7. Guardar intercambio completo
            await self.conversation_helper.save_conversation_exchange(
                tenant_id=chat_request.tenant_id,
                session_id=chat_request.session_id,
                agent_id=chat_request.agent_id,
                history=history,
                user_message=last_user_message,
                assistant_message=response_message,
                task_id=chat_request.task_id,
                ttl=self.action.execution_config.history_ttl,
                metadata={
                    "mode": "advance",
                    "execution_time_seconds": execution_time,
                    "react_iterations": len(iterations_metadata),
                    "iterations_detail": iterations_metadata
                }
            )
            
            self.logger.info(
                "Chat avanzado procesado exitosamente",
                extra={
                    "conversation_id": history.conversation_id,
                    "task_id": str(chat_request.task_id),
                    "execution_time_seconds": execution_time,
                    "react_iterations": len(iterations_metadata),
                    "response_length": len(response_message.content)
                }
            )
            
            return chat_response
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(
                "Error procesando chat avanzado",
                extra={
                    "tenant_id": str(chat_request.tenant_id),
                    "session_id": str(chat_request.session_id),
                    "agent_id": str(chat_request.agent_id),
                    "task_id": str(chat_request.task_id),
                    "execution_time_seconds": execution_time,
                    "error": str(e)
                }
            )
            raise
    
    async def _execute_react_loop(
        self,
        messages: List[ChatMessage],
        chat_request: ChatRequest
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Ejecuta el loop ReAct con herramientas y múltiples iteraciones.
        
        Args:
            messages: Mensajes integrados con historial
            chat_request: Solicitud original de chat
            
        Returns:
            Tupla con (respuesta_final, metadatos_de_iteraciones)
        """
        max_iterations = self.action.execution_config.max_iterations
        timeout_seconds = self.action.execution_config.timeout_seconds
        
        iterations_metadata = []
        current_messages = messages.copy()
        
        self.logger.debug(
            "Iniciando loop ReAct",
            extra={
                "max_iterations": max_iterations,
                "timeout_seconds": timeout_seconds,
                "initial_messages": len(current_messages)
            }
        )
        
        for iteration in range(max_iterations):
            iteration_start = time.time()
            
            try:
                # Preparar payload para query service
                payload = {
                    "messages": [msg.dict() for msg in current_messages],
                    "agent_id": str(chat_request.agent_id),
                    "session_id": str(chat_request.session_id),
                    "task_id": str(chat_request.task_id),
                    "iteration": iteration + 1
                }
                
                # Enviar al query service con timeout
                query_response = await asyncio.wait_for(
                    self.query_client.query_advance(payload),
                    timeout=timeout_seconds
                )
                
                iteration_time = time.time() - iteration_start
                
                # Procesar respuesta
                if query_response.get("tool_calls"):
                    # Hay tool calls, continuar iteración
                    tool_calls = query_response["tool_calls"]
                    
                    # Agregar respuesta del asistente con tool calls
                    assistant_message = ChatMessage(
                        role="assistant",
                        content=query_response.get("content", ""),
                        tool_calls=tool_calls
                    )
                    current_messages.append(assistant_message)
                    
                    # Procesar tool calls y agregar respuestas
                    for tool_call in tool_calls:
                        tool_response = await self._execute_tool_call(tool_call)
                        
                        tool_message = ChatMessage(
                            role="tool",
                            content=str(tool_response.get("result", "")),
                            tool_call_id=tool_call.get("id")
                        )
                        current_messages.append(tool_message)
                    
                    # Registrar iteración
                    iterations_metadata.append({
                        "iteration": iteration + 1,
                        "type": "tool_calls",
                        "tool_calls_count": len(tool_calls),
                        "execution_time_seconds": round(iteration_time, 2),
                        "status": "continued"
                    })
                    
                    self.logger.debug(
                        f"Iteración {iteration + 1}: {len(tool_calls)} tool calls ejecutados",
                        extra={
                            "iteration": iteration + 1,
                            "tool_calls": len(tool_calls),
                            "execution_time": iteration_time
                        }
                    )
                    
                else:
                    # Sin tool calls, respuesta final
                    iterations_metadata.append({
                        "iteration": iteration + 1,
                        "type": "final_response",
                        "execution_time_seconds": round(iteration_time, 2),
                        "status": "completed"
                    })
                    
                    self.logger.debug(
                        f"Iteración {iteration + 1}: respuesta final generada",
                        extra={
                            "iteration": iteration + 1,
                            "execution_time": iteration_time,
                            "response_length": len(query_response.get("content", ""))
                        }
                    )
                    
                    return query_response, iterations_metadata
                    
            except asyncio.TimeoutError:
                iterations_metadata.append({
                    "iteration": iteration + 1,
                    "type": "timeout",
                    "execution_time_seconds": timeout_seconds,
                    "status": "timeout"
                })
                
                self.logger.warning(
                    f"Timeout en iteración {iteration + 1}",
                    extra={
                        "iteration": iteration + 1,
                        "timeout_seconds": timeout_seconds
                    }
                )
                break
                
            except Exception as e:
                iteration_time = time.time() - iteration_start
                iterations_metadata.append({
                    "iteration": iteration + 1,
                    "type": "error",
                    "execution_time_seconds": round(iteration_time, 2),
                    "status": "error",
                    "error": str(e)
                })
                
                self.logger.error(
                    f"Error en iteración {iteration + 1}: {e}",
                    extra={
                        "iteration": iteration + 1,
                        "execution_time": iteration_time,
                        "error": str(e)
                    }
                )
                break
        
        # Si llegamos aquí, se agotaron las iteraciones
        final_response = {
            "content": "Se agotaron las iteraciones máximas sin completar la tarea.",
            "status": "max_iterations_reached"
        }
        
        return final_response, iterations_metadata
    
    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta un tool call específico.
        
        Args:
            tool_call: Definición del tool call a ejecutar
            
        Returns:
            Resultado de la ejecución del tool
        """
        # Placeholder para ejecución de herramientas
        # En implementación real, aquí se ejecutarían las herramientas específicas
        
        tool_name = tool_call.get("function", {}).get("name", "unknown")
        
        self.logger.debug(
            f"Ejecutando tool call: {tool_name}",
            extra={
                "tool_name": tool_name,
                "tool_call_id": tool_call.get("id")
            }
        )
        
        # Simulación de respuesta (debe implementarse según las herramientas reales)
        return {
            "result": f"Tool {tool_name} ejecutada exitosamente",
            "tool_name": tool_name,
            "tool_call_id": tool_call.get("id")
        }