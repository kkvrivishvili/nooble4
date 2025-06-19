"""
Handler para agentes ReAct que utiliza el QueryService para llamadas LLM y tool calling.
"""
import logging
import time
import json
from typing import Dict, Any, List, Optional, Union # Added Union
from datetime import datetime

from common.handlers.base_handler import BaseHandler
from common.config.base_settings import CommonAppSettings
from common.errors.exceptions import ExternalServiceError, ToolExecutionError, AppValidationError

from ..clients.query_client import QueryClient # Changed: Using QueryClient
from ..models.payloads import (
    ExecuteReactPayload, ExecuteReactResponse, 
    ExecutionResult, ExecutionStep, ToolConfig, LLMConfig # Added LLMConfig
)
from ..tools.base_tool import BaseTool
from ..tools.tool_registry import ToolRegistry # Assuming a tool registry exists

# Parser for ReAct thought/action is removed, LLM will use tool_calls directly.

logger = logging.getLogger(__name__)

# Constante para el rol de tool en los mensajes de OpenAI
TOOL_ROLE = "tool"

class ReactHandler(BaseHandler):
    """Handler para agentes ReAct con herramientas, usando QueryService."""

    def __init__(self, app_settings: CommonAppSettings, tool_registry: ToolRegistry):
        super().__init__(app_settings)
        query_url = getattr(app_settings, 'query_service_url', 'http://localhost:8002')
        self.query_client = QueryClient(base_url=query_url)
        self.tool_registry = tool_registry
        self._logger.info(f"ReactHandler inicializado con QueryService URL: {query_url}")

    async def execute_react(
        self,
        payload: ExecuteReactPayload,
        tenant_id: str,
        session_id: str
    ) -> ExecuteReactResponse:
        """
        Ejecuta agente ReAct con loop de pensamiento-acción, usando QueryService para LLM y tool calls.
        """
        start_time = time.time()
        execution_steps: List[ExecutionStep] = []
        tools_used_in_run: List[str] = [] # Renamed for clarity
        total_llm_tokens = 0 # To accumulate token usage
        total_llm_calls = 0

        try:
            self._logger.info(
                f"Iniciando ReAct para agente {payload.agent_id}, "
                f"tenant {tenant_id}, session {session_id}"
            )

            # Obtener herramientas disponibles del payload y formatearlas para el LLM
            available_tools_definitions = self._get_formatted_tools(payload.available_tools)

            # Crear prompt inicial del sistema (si se usa, o se puede omitir si el LLM es bueno con tools)
            system_message_content = self._build_system_prompt(
                payload.react_system_prompt,
                payload.available_tools # Pasamos ToolConfig para la descripción textual
            )

            messages: List[Dict[str, Any]] = []
            if system_message_content:
                messages.append({"role": "system", "content": system_message_content})
            messages.append({"role": "user", "content": payload.user_message})

            final_answer: Optional[str] = None
            iteration = 0

            while iteration < payload.max_iterations and not final_answer:
                iteration += 1
                step_start_time = time.time()
                
                current_step = ExecutionStep(
                    step_number=iteration,
                    thought="", # El LLM podría no generar un 'thought' explícito si usa tools directamente
                    timestamp=datetime.now().isoformat()
                )

                if time.time() - start_time > payload.max_execution_time:
                    self._logger.warning(f"ReAct para {payload.agent_id} excedió max_execution_time.")
                    current_step.observation = "Execution timeout reached."
                    execution_steps.append(current_step)
                    break

                # Llamada al LLM a través de QueryService
                self._logger.debug(f"Iteración {iteration}: Enviando mensajes al LLM: {messages}")
                llm_response_data = await self.query_client.llm_direct(
                    messages=messages,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    llm_config=payload.llm_config.model_dump() if payload.llm_config else None,
                    tools=available_tools_definitions if available_tools_definitions else None,
                    tool_choice=payload.tool_choice # Puede ser 'auto', 'none', o specific
                )
                total_llm_calls += 1
                if llm_response_data.get("total_tokens"):
                    total_llm_tokens += llm_response_data["total_tokens"]
                
                self._logger.debug(f"Iteración {iteration}: Respuesta LLM recibida: {llm_response_data}")

                llm_message_content = llm_response_data.get("response")
                tool_calls = llm_response_data.get("tool_calls")

                # El 'thought' puede ser el contenido del mensaje del LLM si no hay tool_calls
                current_step.thought = llm_message_content if llm_message_content else "No thought provided by LLM."

                # Construir el mensaje del asistente para la próxima iteración
                assistant_message: Dict[str, Any] = {"role": "assistant"}
                if llm_message_content:
                    assistant_message["content"] = llm_message_content
                
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls # Guardar para el historial
                    
                    # Ejecutar herramientas
                    tool_messages_for_next_llm_call: List[Dict[str, str]] = []
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("function", {}).get("name")
                        tool_args_str = tool_call.get("function", {}).get("arguments")
                        tool_call_id = tool_call.get("id") # Necesario para la respuesta de la tool

                        if not tool_name or not tool_args_str or not tool_call_id:
                            self._logger.error(f"Tool call inválido recibido: {tool_call}")
                            observation = f"Error: Tool call inválido: {tool_call}"
                            tool_messages_for_next_llm_call.append({
                                "role": TOOL_ROLE,
                                "tool_call_id": tool_call_id, 
                                "name": tool_name or "unknown_tool",
                                "content": observation
                            })
                            continue
                        
                        current_step.action = tool_name
                        current_step.action_input = tool_args_str # Guardamos el input como string JSON
                        
                        try:
                            tool_input_dict = json.loads(tool_args_str)
                        except json.JSONDecodeError:
                            self._logger.error(f"Error al decodificar JSON para argumentos de tool {tool_name}: {tool_args_str}")
                            observation = f"Error: Argumentos de la herramienta {tool_name} no son JSON válido: {tool_args_str}"
                        else:
                            self._logger.info(f"Ejecutando herramienta: {tool_name} con input: {tool_input_dict}")
                            observation = await self._execute_tool(tool_name, tool_input_dict, tenant_id, session_id)
                            self._logger.info(f"Resultado de herramienta {tool_name}: {observation}")
                        
                        current_step.observation = observation # Última observación del paso
                        if tool_name not in tools_used_in_run:
                            tools_used_in_run.append(tool_name)
                        
                        tool_messages_for_next_llm_call.append({
                            "role": TOOL_ROLE,
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": str(observation) # El contenido debe ser string
                        })
                    
                    messages.append(assistant_message) # Mensaje del asistente con tool_calls
                    messages.extend(tool_messages_for_next_llm_call) # Resultados de las tools
                else:
                    # No hay tool_calls, el LLM debe haber dado la respuesta final o continuar pensando
                    messages.append(assistant_message) # Mensaje del asistente sin tool_calls
                    if llm_message_content:
                        # Asumimos que si no hay tool_calls, el contenido es la respuesta final o un pensamiento continuo.
                        # El prompt debe guiar al LLM para usar "Final Answer:" o similar si es el final.
                        # O, si tool_choice fue 'none', este es el output directo.
                        # O, si el LLM decide responder directamente sin usar tools.
                        final_answer = llm_message_content # Considerar este el final
                        current_step.thought = f"Final Answer: {final_answer}" # Marcar como final en el step
                    else:
                        # Esto es inusual, LLM no dio contenido ni tool_calls
                        self._logger.warning("LLM no devolvió contenido ni tool_calls.")
                        final_answer = "El LLM no proporcionó una respuesta o acción." 
                
                current_step.execution_time_seconds = time.time() - step_start_time
                execution_steps.append(current_step)

                if final_answer: # Salir del loop si ya tenemos respuesta final
                    break
            
            # Fin del loop ReAct
            if not final_answer:
                final_answer = "No se pudo generar una respuesta final dentro de los límites establecidos (iteraciones o tiempo)."
                # Último paso podría no estar en execution_steps si el loop terminó por timeout/iteraciones antes de procesar
                if not execution_steps or execution_steps[-1].step_number != iteration:
                    timeout_step = ExecutionStep(
                        step_number=iteration,
                        thought="Loop terminado por límite de iteraciones o tiempo.",
                        observation=final_answer,
                        timestamp=datetime.now().isoformat(),
                        execution_time_seconds=0
                    )
                    execution_steps.append(timeout_step)

            total_execution_time = time.time() - start_time
            self._logger.info(
                f"ReAct para {payload.agent_id} completado en {total_execution_time:.2f}s. "
                f"Iteraciones: {iteration}. LLM Calls: {total_llm_calls}. Tokens: {total_llm_tokens}."
            )

            execution_result = ExecutionResult(
                success=True, # O determinar basado en si final_answer es satisfactorio
                final_answer=final_answer,
                execution_mode="advanced_tool_calling", # Nuevo modo
                execution_steps=execution_steps,
                total_iterations=iteration,
                execution_time_seconds=total_execution_time,
                total_llm_calls=total_llm_calls,
                total_tokens_used=total_llm_tokens
            )

            return ExecuteReactResponse(
                execution_result=execution_result,
                tools_used=tools_used_in_run,
                session_id=session_id,
                tenant_id=tenant_id
            )

        except ExternalServiceError as ese:
            self._logger.error(f"Error de servicio externo en ReAct para {payload.agent_id}: {ese}", exc_info=True)
            raise
        except ToolExecutionError as tee:
             self._logger.error(f"Error de ejecución de herramienta en ReAct para {payload.agent_id}: {tee}", exc_info=True)
             # Podríamos querer devolver una respuesta parcial aquí
             raise
        except Exception as e:
            self._logger.error(f"Error inesperado en ReAct para {payload.agent_id}: {e}", exc_info=True)
            # Considerar devolver un ExecutionResult con success=False
            raise ExternalServiceError(f"Error interno en ReAct: {str(e)}", original_exception=e)

    def _get_formatted_tools(self, tool_configs: List[ToolConfig]) -> List[Dict[str, Any]]:
        """Formatea las herramientas para la API de OpenAI/Groq."""
        if not tool_configs:
            return []
        
        formatted_tools = []
        for tool_config in tool_configs:
            try:
                # Validar que la herramienta exista en el registro
                tool_instance = self.tool_registry.get_tool(tool_config.name)
                if not tool_instance:
                    self._logger.warning(f"Tool '{tool_config.name}' no encontrada en el registro. Omitiendo.")
                    continue
                
                # Usar el schema de la instancia de la herramienta (que debe ser Pydantic)
                function_schema = tool_instance.get_openapi_schema()
                if not function_schema:
                     self._logger.warning(f"Tool '{tool_config.name}' no pudo generar schema. Omitiendo.")
                     continue

                formatted_tools.append({
                    "type": "function",
                    "function": function_schema
                })
            except Exception as e:
                self._logger.error(f"Error al formatear la herramienta {tool_config.name}: {e}", exc_info=True)
        return formatted_tools

    def _build_system_prompt(
        self, 
        custom_prompt_template: Optional[str], 
        tool_configs: List[ToolConfig] # Usamos ToolConfig para la descripción textual
    ) -> Optional[str]:
        """Construye el prompt del sistema con descripción de herramientas (opcional)."""
        if not custom_prompt_template:
            # Si no hay plantilla, no generamos system prompt sobre tools, confiamos en la lista de tools
            return None 
            
        # Crear una descripción textual de las herramientas para el prompt del sistema
        # Esto es adicional a pasar las definiciones de tools al LLM.
        # Puede ayudar a algunos LLMs a entender mejor cuándo usar las tools.
        tools_description_parts = []
        for tool_cfg in tool_configs:
            tool_instance = self.tool_registry.get_tool(tool_cfg.name)
            description = tool_cfg.description
            if tool_instance and hasattr(tool_instance, 'description') and tool_instance.description:
                description = tool_instance.description # Usar descripción de la instancia si es más rica
            
            # Intentar obtener parámetros del schema para una descripción más detallada
            params_desc = ""
            if tool_instance:
                try:
                    schema = tool_instance.get_openapi_schema()
                    if schema and schema.get('parameters', {}).get('properties'):
                        props = schema['parameters']['properties']
                        params_list = []
                        for p_name, p_details in props.items():
                            p_type = p_details.get('type', 'any')
                            p_desc = p_details.get('description', '')
                            param_str = f"{p_name} ({p_type})" 
                            if p_desc:
                                param_str += f": {p_desc}"
                            params_list.append(param_str)
                        if params_list:
                            params_desc = " Parameters: " + ", ".join(params_list) + "."
                except Exception as e:
                    self._logger.warning(f"No se pudo generar descripción de parámetros para {tool_cfg.name}: {e}") 

            tools_description_parts.append(f"- {tool_cfg.name}: {description}{params_desc}")
        
        tools_description_str = "\n".join(tools_description_parts)
        
        # Usar plantilla por defecto si no se provee una personalizada y hay herramientas
        if not custom_prompt_template and tools_description_str:
            from ..config.constants import REACT_TOOL_SYSTEM_PROMPT # Asumiendo una nueva constante
            custom_prompt_template = REACT_TOOL_SYSTEM_PROMPT
        elif not custom_prompt_template:
            return None # No hay plantilla ni herramientas para describir

        try:
            return custom_prompt_template.format(tools_description=tools_description_str)
        except KeyError:
            self._logger.warning(f"Plantilla de system prompt '{custom_prompt_template}' no contiene 'tools_description'. Usando tal cual.")
            return custom_prompt_template # Devolver sin formatear si falta el placeholder

    async def _execute_tool(
        self, 
        tool_name: str, 
        tool_input: Dict[str, Any],
        tenant_id: str, # Para pasar contexto a la herramienta si es necesario
        session_id: str # Para pasar contexto a la herramienta si es necesario
    ) -> str:
        """Ejecuta una herramienta registrada y devuelve su resultado como string."""
        tool_instance = self.tool_registry.get_tool(tool_name)
        if not tool_instance:
            self._logger.error(f"Herramienta '{tool_name}' no encontrada en el registro.")
            return f"Error: Herramienta '{tool_name}' no encontrada."
        
        try:
            # Pasar contexto adicional si la herramienta lo soporta (ej. con **kwargs o un objeto de contexto)
            # Aquí asumimos que el método execute de la herramienta puede tomar tenant_id y session_id
            # si están definidos en sus parámetros. La herramienta debe manejar esto. 
            # Una forma más robusta sería un objeto de contexto o chequear la signatura.
            
            # Simplificado: la herramienta debe estar diseñada para aceptar **tool_input
            # y opcionalmente tenant_id, session_id si los necesita y declara.
            result = await tool_instance.execute(**tool_input) # Aquí se asume que execute es async
            
            # El resultado de la herramienta debe ser serializable a string para el LLM
            if not isinstance(result, str):
                try:
                    result_str = json.dumps(result)
                except TypeError:
                    self._logger.warning(f"Resultado de herramienta {tool_name} no es serializable a JSON directamente. Usando repr().")
                    result_str = repr(result)
            else:
                result_str = result
            
            # Truncar si es muy largo para evitar exceder límites de token del LLM
            # TODO: Hacer esto configurable
            max_obs_length = 2000 
            if len(result_str) > max_obs_length:
                self._logger.warning(f"Resultado de herramienta {tool_name} truncado a {max_obs_length} caracteres.")
                result_str = result_str[:max_obs_length] + "... (truncado)"
            return result_str
        
        except AppValidationError as ave:
            self._logger.warning(f"Error de validación en input para herramienta {tool_name}: {ave}")
            return f"Error de validación de input para {tool_name}: {str(ave)}"
        except ToolExecutionError as tee:
            self._logger.error(f"Error durante la ejecución de la herramienta {tool_name}: {tee}", exc_info=True)
            return f"Error ejecutando {tool_name}: {str(tee)}"
        except Exception as e:
            self._logger.error(f"Error inesperado ejecutando herramienta {tool_name}: {e}", exc_info=True)
            # No exponer detalles de errores inesperados al LLM directamente por seguridad.
            return f"Error inesperado al ejecutar la herramienta {tool_name}."

    async def close(self):
        """Cierra recursos del handler, como el cliente HTTP."""
        try:
            if hasattr(self.query_client, 'close') and callable(getattr(self.query_client, 'close')):
                await self.query_client.close()
            self._logger.info("ReactHandler cerrado y cliente QueryService cerrado.")
        except Exception as e:
            self._logger.error(f"Error cerrando ReactHandler: {e}", exc_info=True)