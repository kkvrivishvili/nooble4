"""
Query Callback Handler - Envío de callbacks de consultas completadas.

Este módulo maneja:
- Envío de callbacks hacia servicios solicitantes
- Formateo de resultados RAG y búsquedas
- Manejo de errores y timeouts
- Tracking de métricas de consulta
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from common.models.actions import DomainAction
from common.models.execution_context import ExecutionContext
from common.services.domain_queue_manager import DomainQueueManager
from query_service.models.actions import QueryCallbackAction
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QueryCallbackHandler:
    """
    Maneja envío de callbacks de consultas completadas.
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
    
    async def send_query_success_callback(
        self,
        task_id: str,
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        query_result: Dict[str, Any],
        processing_time: float,
        tokens_used: Optional[int] = None,
        context: Optional[ExecutionContext] = None,
        similarity_score: Optional[float] = None,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Envía callback de consulta exitosa.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            query_result: Resultado de la consulta
            processing_time: Tiempo de procesamiento
            tokens_used: Tokens utilizados (opcional)
            context: Contexto de ejecución (opcional)
            similarity_score: Puntuación de similitud (opcional)
            sources: Fuentes de información (opcional)
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback
            callback_action = QueryCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                status="completed",
                result=query_result,
                processing_time=processing_time,
                tokens_used=tokens_used,
                callback_queue=callback_queue,  # Mantener por compatibilidad
                similarity_score=similarity_score,
                sources=sources
            )
            
            # Determinar si usar encolado con contexto o legacy
            if context:
                logger.info(f"Enviando callback de consulta exitosa con contexto. Tenant: {tenant_id}, Tier: {context.tenant_tier}")
                target_domain = callback_queue.split(".")[0] if "." in callback_queue else "generic"
                success = await self.queue_manager.enqueue_execution(
                    action=callback_action,
                    target_domain=target_domain,
                    context=context
                )
            else:
                # Fallback al método legacy
                logger.info(f"Enviando callback de consulta exitosa (legacy). Tenant: {tenant_id}")
                success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de consulta exitosa enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "success", processing_time)
            else:
                logger.error(f"Error enviando callback de consulta: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_query_success_callback: {str(e)}")
            return False
    
    async def send_search_success_callback(
        self,
        task_id: str,
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        search_result: Dict[str, Any],
        processing_time: float,
        context: Optional[ExecutionContext] = None
    ) -> bool:
        """
        Envía callback de búsqueda exitosa.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            search_result: Resultado de la búsqueda
            processing_time: Tiempo de procesamiento
            context: Contexto de ejecución (opcional)
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback para búsqueda
            callback_action = QueryCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                status="completed",
                result=search_result,
                processing_time=processing_time,
                tokens_used=None,  # Búsqueda no usa tokens LLM
                callback_queue=callback_queue
            )
            
            # Determinar si usar encolado con contexto o legacy
            if context:
                logger.info(f"Enviando callback de búsqueda exitosa con contexto. Tenant: {tenant_id}, Tier: {context.tenant_tier}")
                target_domain = callback_queue.split(".")[0] if "." in callback_queue else "generic"
                success = await self.queue_manager.enqueue_execution(
                    action=callback_action,
                    target_domain=target_domain,
                    context=context
                )
            else:
                # Fallback al método legacy
                logger.info(f"Enviando callback de búsqueda exitosa (legacy). Tenant: {tenant_id}")
                success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de búsqueda exitosa enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "search_success", processing_time)
            else:
                logger.error(f"Error enviando callback de búsqueda: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_search_success_callback: {str(e)}")
            return False
    
    async def send_error_callback(
        self,
        task_id: str,
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        error_info: Dict[str, Any],
        processing_time: Optional[float] = None,
        context: Optional[ExecutionContext] = None
    ) -> bool:
        """
        Envía callback de error de consulta.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            error_info: Información del error
            processing_time: Tiempo de procesamiento antes del error
            context: Contexto de ejecución (opcional)
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback de error
            callback_action = QueryCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                status="failed",
                result={
                    "status": "failed",
                    "error": error_info
                },
                processing_time=processing_time,
                tokens_used=None,
                callback_queue=callback_queue
            )
            
            # Determinar si usar encolado con contexto o legacy
            if context:
                logger.info(f"Enviando callback de error con contexto. Tenant: {tenant_id}, Tier: {context.tenant_tier}")
                target_domain = callback_queue.split(".")[0] if "." in callback_queue else "generic"
                success = await self.queue_manager.enqueue_execution(
                    action=callback_action,
                    target_domain=target_domain,
                    context=context
                )
            else:
                # Fallback al método legacy
                logger.info(f"Enviando callback de error (legacy). Tenant: {tenant_id}")
                success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de error enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "error", processing_time)
            else:
                logger.error(f"Error enviando callback de error: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_error_callback: {str(e)}")
            return False
    
    async def _track_callback_sent(
        self, 
        task_id: str, 
        tenant_id: str, 
        callback_type: str,
        processing_time: Optional[float] = None
    ):
        """Registra métricas de callback enviado."""
        if not self.redis:
            return
        
        try:
            # Métricas por tenant
            today = datetime.now().date().isoformat()
            metrics_key = f"query_callbacks:{tenant_id}:{today}"
            
            await self.redis.hincrby(metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 días
            
            # Registrar tiempo de procesamiento si está disponible
            if processing_time is not None:
                await self.redis.lpush(f"query_processing_times:{tenant_id}", processing_time)
                await self.redis.ltrim(f"query_processing_times:{tenant_id}", 0, 999)  # Últimos 1000
            
            # Métricas globales
            global_metrics_key = f"query_callbacks:global:{today}"
            await self.redis.hincrby(global_metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(global_metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(global_metrics_key, 86400 * 30)  # 30 días
            
        except Exception as e:
            logger.error(f"Error tracking query callback: {str(e)}")
    
    async def get_callback_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de callbacks para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"query_callbacks:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            # Obtener tiempos de procesamiento promedio
            processing_times = await self.redis.lrange(f"query_processing_times:{tenant_id}", 0, -1)
            avg_processing_time = 0.0
            if processing_times:
                times = [float(t) for t in processing_times]
                avg_processing_time = sum(times) / len(times)
            
            return {
                "date": today,
                "total_callbacks": int(metrics.get("total_callbacks", 0)),
                "success_callbacks": int(metrics.get("callbacks_success", 0)),
                "search_callbacks": int(metrics.get("callbacks_search_success", 0)),
                "error_callbacks": int(metrics.get("callbacks_error", 0)),
                "success_rate": self._calculate_success_rate(metrics),
                "avg_processing_time": round(avg_processing_time, 3)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo query callback stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_success_rate(self, metrics: Dict[str, str]) -> float:
        """Calcula tasa de éxito de callbacks."""
        total = int(metrics.get("total_callbacks", 0))
        success = int(metrics.get("callbacks_success", 0)) + int(metrics.get("callbacks_search_success", 0))
        
        if total == 0:
            return 0.0
        
        return round((success / total) * 100, 2)