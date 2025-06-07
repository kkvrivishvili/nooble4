"""
Execution Callback Handler - Envío de callbacks de ejecución completada.

Este módulo maneja:
- Envío de callbacks a Agent Orchestrator Service
- Formateo de resultados de ejecución
- Manejo de errores y timeouts
- Tracking de métricas de ejecución
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from agent_execution_service.models.actions_model import ExecutionCallbackAction
from agent_execution_service.models.execution_model import ExecutionResult, ExecutionStatus
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExecutionCallbackHandler:
    """
    Maneja envío de callbacks de ejecución completada.
    """
    
    def __init__(self, queue_manager: DomainQueueManager, redis_client=None):
        """
        Inicializa handler.
        
        Args:
            queue_manager: Gestor de colas por tier
            redis_client: Cliente Redis para tracking (opcional)
        """
        self.queue_manager = queue_manager
        self.redis = redis_client
    
    async def send_success_callback(
        self,
        task_id: str,
        tenant_id: str,
        tenant_tier: str,
        session_id: str,
        callback_queue: str,
        execution_result: ExecutionResult
    ) -> bool:
        """
        Envía callback de ejecución exitosa.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            tenant_tier: Tier del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            execution_result: Resultado de la ejecución
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Formatear resultado para callback
            formatted_result = self._format_execution_result(execution_result)
            
            # Crear acción de callback
            callback_action = ExecutionCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id,
                status="completed",
                result=formatted_result,
                execution_time=execution_result.execution_time,
                tokens_used=self._extract_token_usage(execution_result),
                callback_queue=callback_queue  # No se usa en enqueue_callback pero lo mantenemos
            )
            
            # Enviar callback
            success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de éxito enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "success")
            else:
                logger.error(f"Error enviando callback de éxito: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_success_callback: {str(e)}")
            return False
    
    async def send_error_callback(
        self,
        task_id: str,
        tenant_id: str,
        tenant_tier: str,
        session_id: str,
        callback_queue: str,
        error_info: Dict[str, Any],
        execution_time: Optional[float] = None
    ) -> bool:
        """
        Envía callback de error de ejecución.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            tenant_tier: Tier del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            error_info: Información del error
            execution_time: Tiempo de ejecución antes del error
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback de error
            callback_action = ExecutionCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                tenant_tier=tenant_tier,
                session_id=session_id,
                status="failed",
                result={
                    "status": "failed",
                    "error": error_info
                },
                execution_time=execution_time,
                tokens_used=None,
                callback_queue=callback_queue
            )
            
            # Enviar callback
            success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de error enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "error")
            else:
                logger.error(f"Error enviando callback de error: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_error_callback: {str(e)}")
            return False
    
    def _format_execution_result(self, execution_result: ExecutionResult) -> Dict[str, Any]:
        """Formatea resultado de ejecución para callback."""
        return {
            "response": execution_result.response,
            "sources": execution_result.sources,
            "tool_calls": execution_result.tool_calls,
            "agent_info": execution_result.agent_info,
            "status": execution_result.status.value,
            "iterations_used": execution_result.iterations_used,
            "started_at": execution_result.started_at.isoformat() if execution_result.started_at else None,
            "completed_at": execution_result.completed_at.isoformat() if execution_result.completed_at else None
        }
    
    def _extract_token_usage(self, execution_result: ExecutionResult) -> Optional[Dict[str, int]]:
        """Extrae información de uso de tokens."""
        if execution_result.tokens_used:
            return {
                "total": execution_result.tokens_used,
                "input": execution_result.agent_info.get("input_tokens", 0),
                "output": execution_result.agent_info.get("output_tokens", 0)
            }
        return None
    
    async def _track_callback_sent(self, task_id: str, tenant_id: str, callback_type: str):
        """Registra métricas de callback enviado."""
        if not self.redis:
            return
        
        try:
            # Métricas por tenant
            today = datetime.now().date().isoformat()
            metrics_key = f"execution_callbacks:{tenant_id}:{today}"
            
            await self.redis.hincrby(metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 días
            
            # Métricas globales
            global_metrics_key = f"execution_callbacks:global:{today}"
            await self.redis.hincrby(global_metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(global_metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(global_metrics_key, 86400 * 30)  # 30 días
            
        except Exception as e:
            logger.error(f"Error tracking callback: {str(e)}")
    
    async def get_callback_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de callbacks para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"execution_callbacks:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            return {
                "date": today,
                "total_callbacks": int(metrics.get("total_callbacks", 0)),
                "success_callbacks": int(metrics.get("callbacks_success", 0)),
                "error_callbacks": int(metrics.get("callbacks_error", 0)),
                "success_rate": self._calculate_success_rate(metrics)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo callback stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_success_rate(self, metrics: Dict[str, str]) -> float:
        """Calcula tasa de éxito de callbacks."""
        total = int(metrics.get("total_callbacks", 0))
        success = int(metrics.get("callbacks_success", 0))
        
        if total == 0:
            return 0.0
        
        return round((success / total) * 100, 2)