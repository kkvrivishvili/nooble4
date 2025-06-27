from typing import Dict, Any, Optional
import logging

from common.workers import BaseWorker
from common.models import DomainAction
from common.config import CommonAppSettings
from common.clients import BaseRedisClient
import redis.asyncio as redis_async

from ..services import IngestionService


class IngestionWorker(BaseWorker):
    """Worker for processing ingestion domain actions"""
    
    def __init__(
        self,
        app_settings: CommonAppSettings,
        async_redis_conn: redis_async.Redis,
        redis_client: BaseRedisClient,
        consumer_id_suffix: Optional[str] = None
    ):
        super().__init__(app_settings, async_redis_conn, consumer_id_suffix)
        self.redis_client = redis_client
        self.ingestion_service = None
        self._logger = logging.getLogger(f"{self.service_name}.IngestionWorker")
    
    async def initialize(self):
        """Initialize the worker and its dependencies"""
        # Initialize base worker
        await super().initialize()
        
        # Initialize ingestion service
        self.ingestion_service = IngestionService(
            app_settings=self.app_settings,
            service_redis_client=self.redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        # Initialize the service components (including QdrantHandler)
        await self.ingestion_service.initialize()
        
        self._logger.info("IngestionWorker initialized successfully")
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Route domain actions to the ingestion service
        
        This method implements the abstract method from BaseWorker
        """
        if not self.ingestion_service:
            raise RuntimeError("IngestionService not initialized")
        
        # Log action receipt
        self._logger.info(
            f"Processing action: {action.action_type} "
            f"(task_id: {action.task_id}, tenant_id: {action.tenant_id})"
        )
        
        try:
            # Delegate to service
            result = await self.ingestion_service.process_action(action)
            
            if result:
                self._logger.info(
                    f"Action {action.action_type} processed successfully"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error processing action {action.action_type}: {e}",
                exc_info=True
            )
            raise
