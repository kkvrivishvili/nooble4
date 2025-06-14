"""
Handler para procesar Domain Actions de embeddings.
MODIFICADO: Integración con sistema de colas por tier y nuevos servicios.
"""

import logging
import time
from typing import Dict, Any, Optional

from common.models.execution_context import ExecutionContext
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction
from embedding_service.handlers.context_handler import EmbeddingContextHandler
from embedding_service.services.embedding_processor import EmbeddingProcessor
from embedding_service.services.validation_service import ValidationService
from embedding_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingHandler:
    """
    Handler para procesar acciones de embeddings.
    MODIFICADO: Usar nuevos servicios y context handler.
    """
    
    def __init__(self, context_handler: EmbeddingContextHandler, redis_client=None):
        """
        Inicializa handler.
        
        Args:
            context_handler: Handler de contexto
            redis_client: Cliente Redis (opcional)
        """
        self.context_handler = context_handler
        self.redis = redis_client
        
        # Inicializar servicios
        self.validation_service = ValidationService(redis_client)
        self.embedding_processor = EmbeddingProcessor(self.validation_service, redis_client)
    
    async def handle_generate(self, action: EmbeddingGenerateAction) -> Dict[str, Any]:
        """
        Procesa una acción de generación de embeddings.
        
        Args:
            action: Acción de embedding
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando generación de embeddings para tarea {task_id}")
            
            # 1. Resolver contexto de embedding
            context = await self.context_handler.resolve_embedding_context(
                action.execution_context
            )
            
            # 2. Validar permisos de embedding
            await self.context_handler.validate_embedding_permissions(
                context=context,
                texts=action.texts,
                model=action.model or settings.default_embedding_model
            )
            
            # 3. Procesar embedding
            embedding_result = await self.embedding_processor.process_embedding_request(
                action, context
            )
            
            # 4. Tracking de métricas
            await self._track_embedding_metrics(
                context, action, embedding_result, time.time() - start_time
            )
            
            logger.info(f"Embedding completado: task_id={task_id}, tiempo={time.time() - start_time:.2f}s")
            
            return {
                "success": True,
                "result": embedding_result,
                "execution_time": time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error en embedding {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_validate(self, action: EmbeddingValidateAction) -> Dict[str, Any]:
        """
        Procesa una acción de validación de textos.
        
        Args:
            action: Acción de validación
            
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando validación para tarea {task_id}")
            
            # 1. Resolver contexto de validación
            context = await self.context_handler.resolve_embedding_context(
                action.execution_context
            )
            
            # 2. Realizar validaciones
            validation_result = await self.validation_service.validate_texts(
                texts=action.texts,
                model=action.model or settings.default_embedding_model,
                context=context,
                raise_error=False
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Validación completada en {processing_time:.2f}s")
            
            return {
                "success": True,
                "result": validation_result,
                "execution_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error en validación {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def _track_embedding_metrics(
        self,
        context: ExecutionContext,
        action: EmbeddingGenerateAction,
        result: Dict[str, Any],
        processing_time: float
    ):
        """Registra métricas de embedding."""
        if not self.redis or not settings.enable_embedding_tracking:
            return
        
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            # Métricas por tenant
            tenant_key = f"embedding_metrics:{context.tenant_id}:{today}"
            await self.redis.hincrby(tenant_key, "total_generations", 1)
            await self.redis.hincrby(tenant_key, "total_texts", len(action.texts))
            
            # Tokens utilizados
            if result.get("total_tokens"):
                await self.redis.hincrby(tenant_key, "total_tokens", result["total_tokens"])
            
            # Tiempo de procesamiento por tier
            await self.redis.lpush(f"embedding_times:{context.tenant_tier}", processing_time)
            await self.redis.ltrim(f"embedding_times:{context.tenant_tier}", 0, 999)
            
            # TTL
            await self.redis.expire(tenant_key, 86400 * 7)  # 7 días
            
        except Exception as e:
            logger.error(f"Error tracking embedding metrics: {str(e)}")
    
    async def get_embedding_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de embeddings para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            metrics_key = f"embedding_metrics:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            return {
                "date": today,
                "total_generations": int(metrics.get("total_generations", 0)),
                "total_texts": int(metrics.get("total_texts", 0)),
                "total_tokens": int(metrics.get("total_tokens", 0))
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo embedding stats: {str(e)}")
            return {"error": str(e)}