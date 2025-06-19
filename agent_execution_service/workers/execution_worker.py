"""
Worker para Agent Execution Service.
"""
import logging
from typing import Optional, Dict, Any
from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
import redis.asyncio as redis_async

from ..services.execution_service import ExecutionService
from ..config.settings import ExecutionServiceSettings

logger = logging.getLogger(__name__)

class ExecutionWorker(BaseWorker):
    """Worker para procesar acciones de ejecución de agentes."""

    def __init__(
        self, 
        app_settings: ExecutionServiceSettings, 
        async_redis_conn: redis_async.Redis, 
        consumer_id_suffix: Optional[str] = None
    ):
        super().__init__(app_settings, async_redis_conn, consumer_id_suffix)
        self.execution_service: Optional[ExecutionService] = None

    async def initialize(self):
        """Inicializa el worker y sus dependencias."""
        try:
            # Inicializar el servicio de ejecución
            self.execution_service = ExecutionService(
                app_settings=self.app_settings,
                service_redis_client=self.redis_client,
                direct_redis_conn=self.async_redis_conn
            )
            
            # Inicializar el servicio
            await self.execution_service.initialize()
            
            # Llamar a la inicialización base
            await super().initialize()
            
            logger.info(f"ExecutionWorker ({self.consumer_name}) inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando ExecutionWorker: {e}")
            raise

    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Maneja una DomainAction delegándola al ExecutionService.
        """
        try:
            if not self.execution_service:
                raise RuntimeError("ExecutionService no está inicializado")

            # Log de entrada
            logger.info(
                f"Worker {self.consumer_name} procesando {action.action_type}",
                extra={
                    "action_id": str(action.action_id),
                    "action_type": action.action_type,
                    "tenant_id": action.tenant_id,
                    "session_id": action.session_id
                }
            )

            # Delegar al servicio
            result = await self.execution_service.process_action(action)
            
            # Log de éxito
            logger.info(
                f"Worker {self.consumer_name} completó {action.action_type} exitosamente",
                extra={
                    "action_id": str(action.action_id),
                    "action_type": action.action_type
                }
            )
            
            return result

        except Exception as e:
            logger.error(
                f"Worker {self.consumer_name} error procesando {action.action_id} ({action.action_type}): {e}",
                extra={
                    "action_id": str(action.action_id),
                    "action_type": action.action_type,
                    "error": str(e)
                }
            )
            raise

    async def cleanup(self):
        """Limpia recursos del worker."""
        try:
            if self.execution_service:
                await self.execution_service.cleanup()
            
            logger.info(f"ExecutionWorker ({self.consumer_name}) limpiado correctamente")
        except Exception as e:
            logger.error(f"Error limpiando ExecutionWorker: {e}")