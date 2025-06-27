"""
Worker para Agent Orchestrator Service.

Simplificado ya que la mayoría del procesamiento es por WebSocket.
Solo maneja acciones especiales si las hay.
"""
import logging
from typing import Dict, Any, Optional

from common.workers.base_worker import BaseWorker
from common.models.actions import DomainAction
from common.config.service_settings import OrchestratorSettings
import redis.asyncio as redis_async

from ..services.orchestration_service import OrchestrationService


class OrchestratorWorker(BaseWorker):
    """
    Worker para procesar Domain Actions en Agent Orchestrator.
    
    Principalmente maneja acciones administrativas ya que
    el flujo principal es por WebSocket.
    """
    
    def __init__(
        self,
        app_settings: OrchestratorSettings,
        async_redis_conn: redis_async.Redis,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el OrchestratorWorker.
        
        Args:
            app_settings: Configuración de la aplicación
            async_redis_conn: Conexión Redis asíncrona
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        super().__init__(app_settings, async_redis_conn, consumer_id_suffix)
        self.orchestration_service: Optional[OrchestrationService] = None
        
    async def initialize(self):
        """Inicializa el worker y sus dependencias."""
        await super().initialize()
        
        # Inicializar servicio de orquestación
        from common.clients.base_redis_client import BaseRedisClient
        
        redis_client = BaseRedisClient(
            service_name=self.app_settings.service_name,
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )
        
        self.orchestration_service = OrchestrationService(
            app_settings=self.app_settings,
            service_redis_client=redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        self.logger.info(f"OrchestratorWorker inicializado correctamente")
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Maneja las acciones de dominio delegando al servicio.
        """
        if not self.orchestration_service:
            raise RuntimeError("OrchestrationService no está inicializado")
        
        self.logger.info(f"Procesando acción: {action.action_type}")
        
        try:
            # Delegar al servicio
            result = await self.orchestration_service.process_action(action)
            return result
            
        except Exception as e:
            self.logger.error(
                f"Error procesando acción {action.action_type}: {e}",
                exc_info=True
            )
            raise