"""
Servicio de negocio para procesar las operaciones de embeddings.

Esta clase encapsula la lógica de negocio para la generación y validación
de embeddings, siendo utilizada por el EmbeddingWorker.
"""

import logging
import time
from typing import Dict, Any

from common.models.execution_context import ExecutionContext
from embedding_service.models.actions import EmbeddingGenerateAction, EmbeddingValidateAction
from embedding_service.handlers.context_handler import EmbeddingContextHandler
from embedding_service.services.embedding_processor import EmbeddingProcessor
from embedding_service.services.validation_service import ValidationService
from embedding_service.config.config import EmbeddingSettings
from common.services import BaseService

logger = logging.getLogger(__name__)


class GenerationService(BaseService):
    """
    Servicio que encapsula la lógica de negocio para las acciones de embeddings.
    Hereda de BaseService para asegurar un contrato común y recibir dependencias.
    """

    def __init__(
        self,
        app_settings: EmbeddingSettings,
        context_handler: EmbeddingContextHandler,
        redis_client=None,
    ):
        """
        Inicializa el servicio de generación.

        Args:
            app_settings: Configuración de la aplicación (inyectada).
            context_handler: Handler de contexto para resolver y validar permisos.
            redis_client: Cliente Redis (opcional).
        """
        super().__init__(app_settings=app_settings, redis_client=redis_client)
        self.context_handler = context_handler

        # Inicializar sub-servicios utilizando las dependencias de la clase base
        self.validation_service = ValidationService(self.redis_client)
        self.embedding_processor = EmbeddingProcessor(
            self.validation_service, self.redis_client
        )

    async def generate_embeddings(self, action: EmbeddingGenerateAction) -> Dict[str, Any]:
        """
        Procesa una solicitud de generación de embeddings.

        Args:
            action: Acción de embedding con los datos necesarios.

        Returns:
            Dict con el resultado del procesamiento.
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
                model=action.model or self.app_settings.default_embedding_model,
            )

            # 3. Procesar embedding
            embedding_result = await self.embedding_processor.process_embedding_request(
                action, context
            )

            # 4. Tracking de métricas
            await self._track_embedding_metrics(
                context, action, embedding_result, time.time() - start_time
            )

            logger.info(
                f"Embedding completado: task_id={task_id}, tiempo={time.time() - start_time:.2f}s"
            )

            return {
                "success": True,
                "result": embedding_result,
                "execution_time": time.time() - start_time,
            }

        except Exception as e:
            logger.error(f"Error en embedding {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                },
            }

    async def validate_embeddings(self, action: EmbeddingValidateAction) -> Dict[str, Any]:
        """
        Valida si un tenant puede procesar una solicitud de embedding.

        Args:
            action: Acción de validación con los datos necesarios.

        Returns:
            Dict con el resultado de la validación.
        """
        start_time = time.time()
        task_id = action.task_id

        try:
            logger.info(f"Procesando validación de embeddings para tarea {task_id}")

            # 1. Resolver contexto
            context = await self.context_handler.resolve_embedding_context(
                action.execution_context
            )

            # 2. Validar permisos
            await self.context_handler.validate_embedding_permissions(
                context=context,
                texts=action.texts,
                model=action.model or self.app_settings.default_embedding_model,
            )

            logger.info(f"Validación de embedding completada para tarea {task_id}")

            return {
                "success": True,
                "result": {"message": "Validation successful"},
                "execution_time": time.time() - start_time,
            }

        except Exception as e:
            logger.error(f"Error en validación de embedding {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                },
            }

    async def _track_embedding_metrics(
        self, context, action, result, execution_time
    ):
        """Placeholder para tracking de métricas."""
        logger.info(
            f"Métricas de embedding: tenant={context.tenant.id}, "
            f"model={action.model}, tokens={result.get('total_tokens', 0)}, "
            f"tiempo={execution_time:.2f}s"
        )
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
            await self.redis.lpush(f"embedding_times:{context.tenant_tier}", duration)
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