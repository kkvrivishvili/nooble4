"""
Handlers para acciones específicas de Agent Execution Service.

Implementa los handlers para procesar los diferentes tipos de Domain Actions
que puede recibir el servicio de ejecución de agentes.
"""

import logging
from typing import Dict, Any
import time
from uuid import uuid4

from agent_execution_service.models.actions_model import AgentExecutionAction
from agent_execution_service.services.agent_executor import AgentExecutor

logger = logging.getLogger(__name__)

class ExecutionHandler:
    """Handler para acciones de ejecución de agentes."""
    
    def __init__(self, agent_service):
        """
        Inicializa el handler con servicios necesarios.
        
        Args:
            agent_service: Servicio que gestiona los agentes
        """
        self.agent_service = agent_service
        self.executor = AgentExecutor(agent_service)
    
    async def handle_agent_run(self, action: AgentExecutionAction) -> Dict[str, Any]:
        """
        Procesa una acción de ejecución de agente.
        
        Args:
            action: Acción de ejecución
            
        Returns:
            Diccionario con resultado
        """
        start_time = time.time()
        task_id = str(uuid4())
        
        try:
            logger.info(f"Procesando ejecución para agente {action.agent_id}, tarea {task_id}")
            
            # Validar parámetros mínimos
            if not action.agent_id or not action.message:
                raise ValueError("Se requiere agent_id y message")
                
            # Ejecutar agente
            execution_result = await self.executor.execute_agent(
                agent_id=action.agent_id,
                message=action.message,
                session_id=action.session_id,
                conversation_id=action.conversation_id,
                user_info=action.user_info,
                context=action.context,
                timeout=action.timeout,
                max_iterations=action.max_iterations
            )
            
            # Medir tiempo total
            execution_time = time.time() - start_time
            
            # Generar resultado exitoso
            return {
                "success": True,
                "task_id": task_id,
                "result": execution_result.dict(),
                "execution_time": execution_time
            }
            
        except Exception as e:
            logger.error(f"Error ejecutando agente: {str(e)}")
            return {
                "success": False,
                "task_id": task_id,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
