"""
Agent Execution Handler - Lógica principal de ejecución de agentes.

Este módulo maneja:
- Orquestación de ejecución de agentes
- Gestión de herramientas y memoria
- Timeouts y límites por tier
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from common.models.execution_context import ExecutionContext
from agent_execution_service.models.actions_model import AgentExecutionAction
from agent_execution_service.models.execution_model import ExecutionResult, ExecutionStatus
from agent_execution_service.handlers.context_handler import ExecutionContextHandler
from agent_execution_service.services.agent_executor import AgentExecutor
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentExecutionHandler:
    """
    Handler principal para ejecución de agentes.
    """
    
    def __init__(self, context_handler: ExecutionContextHandler, redis_client=None):
        """
        Inicializa handler.
        
        Args:
            context_handler: Handler de contexto
            redis_client: Cliente Redis (opcional)
        """
        self.context_handler = context_handler
        self.redis = redis_client
        self.settings = settings  # Guardar referencia a configuraciones
        
        # Inicializar executor de agentes
        self.agent_executor = AgentExecutor(context_handler, redis_client)
    
    async def handle_agent_execution(self, action: AgentExecutionAction, context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
        """
        Maneja ejecución completa de agente.
        
        Args:
            action: Acción de ejecución
            context: Contexto de ejecución (opcional)
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Iniciando ejecución de agente: task_id={task_id}")
            
            # 1. Usar contexto proporcionado o resolverlo
            if not context:
                logger.info("Resolviendo contexto de ejecución desde la acción")
                context = await self.context_handler.resolve_execution_context(
                    action.execution_context
                )
            else:
                logger.info(f"Usando contexto de ejecución proporcionado. Tier: {context.tenant_tier}")
            
            # 2. Obtener configuración del agente (con caché)
            agent_config = await self.context_handler.get_agent_config(
                agent_id=context.primary_agent_id,
                tenant_id=context.tenant_id,
                session_id=action.session_id
            )
            
            # 3. Validar permisos de ejecución
            await self.context_handler.validate_execution_permissions(context, agent_config)
            
            # 4. Obtener historial de conversación
            # Detectar si es una nueva conversación revisando si hay algún mensaje previo en la acción
            is_new_conversation = not action.conversation_history 
            
            conversation_history = await self.context_handler.get_conversation_history(
                session_id=action.session_id,
                tenant_id=action.tenant_id,
                limit=agent_config.get("max_history_messages", 10),
                is_new_conversation=is_new_conversation,
                tenant_tier=context.tenant_tier
            )
            
            # 5. Configurar timeout según tier
            execution_timeout = self._get_execution_timeout(context.tenant_tier, action.timeout)
            
            # 6. Ejecutar agente con timeout
            execution_result = await asyncio.wait_for(
                self.agent_executor.execute_agent(
                    context=context,
                    agent_config=agent_config,
                    message=action.message,
                    message_type=action.message_type,
                    conversation_history=conversation_history,
                    user_info=action.user_info,
                    max_iterations=action.max_iterations
                ),
                timeout=execution_timeout
            )
            
            # 7. Guardar mensaje en conversación
            await self._save_conversation_messages(
                action, execution_result, time.time() - start_time
            )
            
            # 8. Tracking de métricas
            await self._track_execution_metrics(
                context, execution_result, time.time() - start_time
            )
            
            logger.info(f"Ejecución completada: task_id={task_id}, tiempo={time.time() - start_time:.2f}s")
            
            return {
                "success": True,
                "execution_result": execution_result,
                "execution_time": time.time() - start_time
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout en ejecución: task_id={task_id}")
            return {
                "success": False,
                "error": {
                    "type": "TimeoutError",
                    "message": f"Ejecución excedió el tiempo límite de {execution_timeout}s"
                },
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en ejecución: task_id={task_id}, error={str(e)}")
            return {
                "success": False,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                },
                "execution_time": time.time() - start_time
            }
    
    def _get_execution_timeout(self, tenant_tier: str, custom_timeout: Optional[int]) -> int:
        """Obtiene timeout de ejecución según tier."""
        # Timeouts por tier
        tier_timeouts = {
            "free": 30,
            "advance": 60,
            "professional": 120,
            "enterprise": 300
        }
        
        tier_timeout = tier_timeouts.get(tenant_tier, 30)
        
        # Usar timeout personalizado si es menor que el del tier
        if custom_timeout:
            return min(custom_timeout, tier_timeout)
        
        return tier_timeout
    
    async def _save_conversation_messages(
        self,
        action: AgentExecutionAction,
        execution_result: ExecutionResult,
        processing_time: float
    ):
        """Guarda mensajes en el historial de conversación con soporte de caché local."""
        try:
            # Obtener el tier del tenant desde el contexto
            tenant_tier = action.execution_context.get("tenant_tier", "free")
            
            # Guardar mensaje del usuario en caché local y servicio (asíncrono/síncrono según tier)
            await self.context_handler.save_conversation_message(
                session_id=action.session_id,
                tenant_id=action.tenant_id,
                role="user",
                content=action.message,
                message_type=action.message_type,
                metadata=action.user_info,
                processing_time=None,
                tenant_tier=tenant_tier  # Usar tier para configuraciones específicas
            )
            
            # Guardar respuesta del agente en caché local y servicio
            if execution_result.response:
                await self.context_handler.save_conversation_message(
                    session_id=action.session_id,
                    tenant_id=action.tenant_id,
                    role="assistant",
                    content=execution_result.response,
                    message_type="text",
                    metadata={
                        "agent_id": execution_result.agent_info.get("agent_id"),
                        "sources": execution_result.sources,
                        "tool_calls": len(execution_result.tool_calls),
                        "iterations": execution_result.iterations_used
                    },
                    processing_time=processing_time,
                    tenant_tier=tenant_tier  # Usar tier para configuraciones específicas
                )
            
        except Exception as e:
            logger.error(f"Error guardando conversación: {str(e)}")
            # No fallar la ejecución por problema de persistencia
    
    async def _track_execution_metrics(
        self,
        context: ExecutionContext,
        execution_result: ExecutionResult,
        execution_time: float
    ):
        """Registra métricas de ejecución."""
        if not self.redis:
            return
        
        try:
            today = datetime.now().date().isoformat()
            
            # Métricas por tenant
            tenant_key = f"execution_metrics:{context.tenant_id}:{today}"
            await self.redis.hincrby(tenant_key, "total_executions", 1)
            await self.redis.hincrby(tenant_key, f"status_{execution_result.status.value}", 1)
            
            # Tiempo de ejecución promedio
            await self.redis.lpush(f"execution_times:{context.tenant_tier}", execution_time)
            await self.redis.ltrim(f"execution_times:{context.tenant_tier}", 0, 999)  # Últimos 1000
            
            # Métricas por tier
            tier_key = f"execution_metrics:tier:{context.tenant_tier}:{today}"
            await self.redis.hincrby(tier_key, "total_executions", 1)
            await self.redis.hincrby(tier_key, f"status_{execution_result.status.value}", 1)
            
            # TTL de métricas
            await self.redis.expire(tenant_key, 86400 * 7)  # 7 días
            await self.redis.expire(tier_key, 86400 * 30)  # 30 días
            
        except Exception as e:
            logger.error(f"Error tracking execution metrics: {str(e)}")
    
    async def get_execution_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de ejecución para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"execution_metrics:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            return {
                "date": today,
                "total_executions": int(metrics.get("total_executions", 0)),
                "completed": int(metrics.get("status_completed", 0)),
                "failed": int(metrics.get("status_failed", 0)),
                "timeout": int(metrics.get("status_timeout", 0)),
                "success_rate": self._calculate_success_rate(metrics)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo execution stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_success_rate(self, metrics: Dict[str, str]) -> float:
        """Calcula tasa de éxito de ejecuciones."""
        total = int(metrics.get("total_executions", 0))
        completed = int(metrics.get("status_completed", 0))
        
        if total == 0:
            return 0.0
        
        return round((completed / total) * 100, 2)
        
    async def handle_session_closed(self, tenant_id: str, session_id: str, tenant_tier: str = "free") -> Dict[str, Any]:
        """
        Este método ha sido deshabilitado intencionalmente.
        Se mantiene la firma para compatibilidad con el código existente.
        
        Args:
            tenant_id: ID del tenant (no utilizado)
            session_id: ID de la sesión cerrada (no utilizado)
            tenant_tier: Nivel de servicio del tenant (no utilizado)
            
        Returns:
            Dict con resultado de la operación, siempre éxito
        """
        logger.debug(f"Método handle_session_closed deshabilitado para sesión {session_id}")
            
        # Devolver un resultado exitoso para mantener compatibilidad
        return {
            "success": True,
            "message": f"Método handle_session_closed deshabilitado"
        }