"""
Agent Executor - Orquestador principal de ejecución de agentes.

Coordina la ejecución de agentes usando LangChain y servicios externos.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from common.models.execution_context import ExecutionContext
from agent_execution_service.models.execution_model import ExecutionResult, ExecutionStatus
from agent_execution_service.services.langchain_integrator import LangChainIntegrator
from agent_execution_service.handlers.context_handler import ExecutionContextHandler
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentExecutor:
    """
    Ejecutor principal de agentes.
    
    Coordina la ejecución usando LangChain y maneja la integración
    con servicios externos como embeddings y query.
    """
    
    def __init__(self, context_handler: ExecutionContextHandler, redis_client=None):
        """
        Inicializa executor.
        
        Args:
            context_handler: Handler de contexto
            redis_client: Cliente Redis para tracking
        """
        self.context_handler = context_handler
        self.redis = redis_client
        
        # Inicializar integrador de LangChain
        self.langchain_integrator = LangChainIntegrator(redis_client)
    
    async def execute_agent(
        self,
        context: ExecutionContext,
        agent_config: Dict[str, Any],
        message: str,
        message_type: str = "text",
        conversation_history: List[Dict[str, Any]] = None,
        user_info: Dict[str, Any] = None,
        max_iterations: Optional[int] = None
    ) -> ExecutionResult:
        """
        Ejecuta agente con configuración específica.
        
        Args:
            context: Contexto de ejecución
            agent_config: Configuración del agente
            message: Mensaje del usuario
            message_type: Tipo de mensaje
            conversation_history: Historial de conversación
            user_info: Información del usuario
            max_iterations: Máximo de iteraciones
            
        Returns:
            ExecutionResult con el resultado de la ejecución
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Ejecutando agente {context.primary_agent_id} para tenant {context.tenant_id}")
            
            # Crear resultado inicial
            execution_result = ExecutionResult(
                task_id=context.context_id,
                status=ExecutionStatus.RUNNING,
                started_at=start_time,
                agent_info={
                    "agent_id": context.primary_agent_id,
                    "agent_name": agent_config.get("name", ""),
                    "agent_type": agent_config.get("type", "conversational"),
                    "model": agent_config.get("model", settings.default_agent_type)
                }
            )
            
            # Configurar parámetros de ejecución
            execution_params = self._prepare_execution_params(
                context, agent_config, max_iterations
            )
            
            # Ejecutar con LangChain
            langchain_result = await self.langchain_integrator.execute_agent(
                agent_config=agent_config,
                message=message,
                conversation_history=conversation_history or [],
                user_info=user_info or {},
                execution_context=context,
                **execution_params
            )
            
            # Procesar resultado
            execution_result.status = ExecutionStatus.COMPLETED
            execution_result.response = langchain_result.get("response", "")
            execution_result.tool_calls = langchain_result.get("tool_calls", [])
            execution_result.sources = langchain_result.get("sources", [])
            execution_result.iterations_used = langchain_result.get("iterations_used", 1)
            execution_result.tokens_used = langchain_result.get("tokens_used")
            execution_result.completed_at = datetime.utcnow()
            execution_result.execution_time = (
                execution_result.completed_at - start_time
            ).total_seconds()
            
            # Actualizar información del agente con métricas
            execution_result.agent_info.update({
                "model_used": langchain_result.get("model_used"),
                "input_tokens": langchain_result.get("input_tokens", 0),
                "output_tokens": langchain_result.get("output_tokens", 0),
                "total_tokens": langchain_result.get("total_tokens", 0)
            })
            
            logger.info(
                f"Agente ejecutado exitosamente: {context.primary_agent_id}, "
                f"tiempo={execution_result.execution_time:.2f}s"
            )
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error ejecutando agente {context.primary_agent_id}: {str(e)}")
            
            # Crear resultado de error
            execution_result.status = ExecutionStatus.FAILED
            execution_result.error = {
                "type": type(e).__name__,
                "message": str(e)
            }
            execution_result.completed_at = datetime.utcnow()
            execution_result.execution_time = (
                execution_result.completed_at - start_time
            ).total_seconds()
            
            return execution_result
    
    def _prepare_execution_params(
        self,
        context: ExecutionContext,
        agent_config: Dict[str, Any],
        max_iterations: Optional[int]
    ) -> Dict[str, Any]:
        """Prepara parámetros de ejecución según tier y configuración."""
        
        # Límites por tier
        tier_limits = {
            "free": {"max_iterations": 3, "max_tools": 2, "timeout": 30},
            "advance": {"max_iterations": 5, "max_tools": 5, "timeout": 60},
            "professional": {"max_iterations": 10, "max_tools": 10, "timeout": 120},
            "enterprise": {"max_iterations": 20, "max_tools": None, "timeout": 300}
        }
        
        limits = tier_limits.get(context.tenant_tier, tier_limits["free"])
        
        # Configurar parámetros
        params = {
            "max_iterations": min(
                max_iterations or agent_config.get("max_iterations", 5),
                limits["max_iterations"]
            ),
            "timeout": limits["timeout"],
            "tenant_tier": context.tenant_tier,
            "collections": context.collections
        }
        
        # Configurar herramientas según tier
        if limits["max_tools"] is not None:
            available_tools = agent_config.get("tools", [])[:limits["max_tools"]]
            params["available_tools"] = available_tools
        else:
            params["available_tools"] = agent_config.get("tools", [])
        
        return params