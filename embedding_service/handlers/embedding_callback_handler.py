"""
Embedding Callback Handler - Envío de callbacks de embeddings completados.

Este módulo maneja:
- Envío de callbacks hacia servicios solicitantes
- Formateo de resultados de embeddings
- Manejo de errores y timeouts
- Tracking de métricas de embedding
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from embedding_service.models.actions import EmbeddingCallbackAction
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingCallbackHandler:
    """
    Maneja envío de callbacks de embeddings completados.
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
        session_id: str,
        callback_queue: str,
        embeddings: List[List[float]],
        model: str,
        dimensions: int,
        total_tokens: int,
        processing_time: float
    ) -> bool:
        """
        Envía callback de embedding exitoso.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            embeddings: Embeddings generados
            model: Modelo usado
            dimensions: Dimensiones de los vectores
            total_tokens: Tokens utilizados
            processing_time: Tiempo de procesamiento
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback
            callback_action = EmbeddingCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                status="completed",
                embeddings=embeddings,
                model=model,
                dimensions=dimensions,
                total_tokens=total_tokens,
                processing_time=processing_time,
                callback_queue=callback_queue  # Mantener por compatibilidad
            )
            
            # Enviar callback
            success = await self.queue_manager.enqueue_callback(callback_action, callback_queue)
            
            if success:
                logger.info(f"Callback de embedding exitoso enviado: task_id={task_id}")
                await self._track_callback_sent(task_id, tenant_id, "success", processing_time)
            else:
                logger.error(f"Error enviando callback de embedding: task_id={task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error en send_success_callback: {str(e)}")
            return False
    
    async def send_error_callback(
        self,
        task_id: str,
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        error_info: Dict[str, Any],
        processing_time: Optional[float] = None
    ) -> bool:
        """
        Envía callback de error de embedding.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola destino del callback
            error_info: Información del error
            processing_time: Tiempo de procesamiento antes del error
            
        Returns:
            True si se envió correctamente
        """
        try:
            # Crear acción de callback de error
            callback_action = EmbeddingCallbackAction(
                task_id=task_id,
                tenant_id=tenant_id,
                session_id=session_id,
                status="failed",
                embeddings=[],
                model="",
                dimensions=0,
                total_tokens=0,
                processing_time=processing_time or 0.0,
                error=error_info,
                callback_queue=callback_queue
            )
            
            # Enviar callback
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
            metrics_key = f"embedding_callbacks:{tenant_id}:{today}"
            
            await self.redis.hincrby(metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 días
            
            # Registrar tiempo de procesamiento si está disponible
            if processing_time is not None:
                await self.redis.lpush(f"embedding_processing_times:{tenant_id}", processing_time)
                await self.redis.ltrim(f"embedding_processing_times:{tenant_id}", 0, 999)  # Últimos 1000
            
            # Métricas globales
            global_metrics_key = f"embedding_callbacks:global:{today}"
            await self.redis.hincrby(global_metrics_key, "total_callbacks", 1)
            await self.redis.hincrby(global_metrics_key, f"callbacks_{callback_type}", 1)
            await self.redis.expire(global_metrics_key, 86400 * 30)  # 30 días
            
        except Exception as e:
            logger.error(f"Error tracking embedding callback: {str(e)}")
    
    async def get_callback_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de callbacks para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"embedding_callbacks:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            # Obtener tiempos de procesamiento promedio
            processing_times = await self.redis.lrange(f"embedding_processing_times:{tenant_id}", 0, -1)
            avg_processing_time = 0.0
            if processing_times:
                times = [float(t) for t in processing_times]
                avg_processing_time = sum(times) / len(times)
            
            return {
                "date": today,
                "total_callbacks": int(metrics.get("total_callbacks", 0)),
                "success_callbacks": int(metrics.get("callbacks_success", 0)),
                "error_callbacks": int(metrics.get("callbacks_error", 0)),
                "success_rate": self._calculate_success_rate(metrics),
                "avg_processing_time": round(avg_processing_time, 3)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo embedding callback stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_success_rate(self, metrics: Dict[str, str]) -> float:
        """Calcula tasa de éxito de callbacks."""
        total = int(metrics.get("total_callbacks", 0))
        success = int(metrics.get("callbacks_success", 0))
        
        if total == 0:
            return 0.0
        
        return round((success / total) * 100, 2)