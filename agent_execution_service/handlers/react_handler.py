"""
Handler para agentes ReAct.
"""
import logging
import time
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from common.handlers.base_handler import BaseHandler
from common.config.base_settings import CommonAppSettings
from ..clients.llm_client import LLMClient
from ..models.payloads import (
    ExecuteReactPayload, ExecuteReactResponse, 
    ExecutionResult, ExecutionStep, ToolConfig
)
from ..tools.base_tool import BaseTool
from ..utils.parsers import ReactParser

logger = logging.getLogger(__name__)

class ReactHandler(BaseHandler):
    """Handler para agentes ReAct con herramientas."""

    def __init__(self, app_settings: CommonAppSettings):
        super().__init__(app_settings)
        self.llm_client: Optional[LLMClient] = None
        self.available_tools: Dict[str, BaseTool] = {}
        self.parser = ReactParser()

    async def setup(self, api_key: str, provider: str = "groq"):
        """Configura el cliente LLM."""
        self.llm_client = LLMClient(provider=provider, api_key=api_key)

    async def execute_react(
        self,
        payload: ExecuteReactPayload,
        tenant_id: str,
        session_id: str
    ) -> ExecuteReactResponse:
        """
        Ejecuta agente ReAct con loop de pensamiento-acción.
        """
        start_time = time.time()
        execution_steps = []
        tools_used = []

        try:
            self._logger.info(
                f"Iniciando ReAct para agente {payload.agent_id}, "
                f"tenant {tenant_id}, session {session_id}"
            )

            # Configurar herramientas disponibles
            self._setup_tools(payload.available_tools)

            # Crear prompt inicial del sistema
            system_prompt = self._build_system_prompt(
                payload.react_system_prompt,
                payload.available_tools
            )

            # Inicializar conversación
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload.user_message}
            ]

            final_answer = None
            iteration = 0

            # Loop principal ReAct
            while iteration < payload.max_iterations and not final_answer:
                iteration += 1
                
                # Verificar timeout
                if time.time() - start_time > payload.max_execution_time:
                    break

                step = await self._execute_react_step(
                    messages, iteration, payload.llm_config
                )
                execution_steps.append(step)

                # Procesar el paso
                if step.action and step.action_input:
                    # Ejecutar herramienta
                    tool_result = await self._execute_tool(
                        step.action, step.action_input
                    )
                    step.observation = tool_result
                    
                    if step.action not in tools_used:
                        tools_used.append(step.action)

                    # Agregar observación a mensajes
                    messages.append({
                        "role": "assistant", 
                        "content": f"Thought: {step.thought}\nAction: {step.action}\nAction Input: {step.action_input}"
                    })
                    messages.append({
                        "role": "user", 
                        "content": f"Observation: {step.observation}"
                    })

                elif "final answer:" in (step.thought or "").lower():
                    # Extraer respuesta final
                    final_answer = self._extract_final_answer(step.thought)
                    break

            if not final_answer:
                final_answer = "No se pudo generar una respuesta final dentro de los límites establecidos."

            execution_time = time.time() - start_time

            execution_result = ExecutionResult(
                success=True,
                final_answer=final_answer,
                execution_mode="advanced",
                execution_steps=execution_steps,
                total_iterations=iteration,
                execution_time_seconds=execution_time
            )

            return ExecuteReactResponse(
                execution_result=execution_result,
                tools_used=tools_used
            )

        except Exception as e:
            self._logger.error(f"Error en ReAct: {e}")
            raise

    async def _execute_react_step(
        self, 
        messages: List[Dict[str, str]], 
        step_number: int,
        llm_config: Optional[Dict[str, Any]]
    ) -> ExecutionStep:
        """Ejecuta un paso individual del loop ReAct."""
        
        # Configuración LLM
        config = llm_config or {}
        model = config.get("model_name", "llama-3.3-70b-versatile")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 1024)

        # Generar respuesta del LLM
        response = await self.llm_client.generate_response(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response["choices"][0]["message"]["content"]
        
        # Parsear respuesta
        parsed = self.parser.parse_react_response(content)

        return ExecutionStep(
            step_number=step_number,
            thought=parsed.get("thought"),
            action=parsed.get("action"),
            action_input=parsed.get("action_input"),
            timestamp=datetime.now().isoformat()
        )

    def _setup_tools(self, tool_configs: List[ToolConfig]):
        """Configura las herramientas disponibles."""
        # Implementar registro de herramientas
        pass

    def _build_system_prompt(
        self, 
        custom_prompt: Optional[str], 
        tools: List[ToolConfig]
    ) -> str:
        """Construye el prompt del sistema con descripción de herramientas."""
        from ..config.constants import REACT_SYSTEM_PROMPT
        
        tools_description = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in tools
        ])
        
        base_prompt = custom_prompt or REACT_SYSTEM_PROMPT
        return base_prompt.format(tools_description=tools_description)

    async def _execute_tool(
        self, 
        tool_name: str, 
        tool_input: Dict[str, Any]
    ) -> str:
        """Ejecuta una herramienta."""
        if tool_name in self.available_tools:
            tool = self.available_tools[tool_name]
            try:
                result = await tool.execute(tool_input)
                return result
            except Exception as e:
                return f"Error ejecutando {tool_name}: {str(e)}"
        else:
            return f"Herramienta '{tool_name}' no encontrada"

    def _extract_final_answer(self, thought: str) -> str:
        """Extrae la respuesta final del pensamiento."""
        if not thought:
            return "No se pudo extraer respuesta final"
            
        # Buscar "Final Answer:" en el texto
        match = re.search(r"final answer:\s*(.*)", thought, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return thought

    async def close(self):
        """Cierra recursos del handler."""
        if self.llm_client:
            await self.llm_client.close()