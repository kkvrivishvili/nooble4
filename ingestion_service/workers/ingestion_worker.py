"""
Worker principal del Ingestion Service.

Implementa BaseWorker para consumir DomainActions del stream Redis
y delegar el procesamiento al IngestionService.
"""

import logging
from typing import Dict, Any, Optional

from common.workers import BaseWorker
from common.models import DomainAction
from common.config import CommonAppSettings
from common.clients import BaseRedisClient
import redis.asyncio as redis_async

from ..services.ingestion_service import IngestionService
from common.config.service_settings import IngestionServiceSettings


class IngestionWorker(BaseWorker):
    """
    Worker que procesa acciones de ingestión desde Redis Streams.
    
    Consume DomainActions del stream del Ingestion Service y las
    procesa usando IngestionService.
    """
    
    def __init__(
        self,
        app_settings: Optional[IngestionServiceSettings] = None,
        async_redis_conn: Optional[redis_async.Redis] = None,
        redis_client: Optional[BaseRedisClient] = None,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el IngestionWorker.
        
        Args:
            app_settings: Configuración del servicio (opcional, se cargará si no se proporciona)
            async_redis_conn: Conexión Redis asíncrona (requerida si no se proporciona redis_client)
            redis_client: Cliente Redis (opcional, se usará si se proporciona)
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        # Cargar configuración si no se proporciona
        if app_settings is None:
            app_settings = IngestionServiceSettings()
            
        if async_redis_conn is None and redis_client is None:
            raise ValueError("Se requiere al menos una conexión Redis (async_redis_conn o redis_client)")
            
        # Inicializar BaseWorker
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn or redis_client.redis_client,
            consumer_id_suffix=consumer_id_suffix
        )
        
        # Inicializar cliente Redis si no se proporcionó
        self.redis_client = redis_client or BaseRedisClient(
            service_name=self.service_name,
            redis_client=async_redis_conn,
            settings=app_settings
        )
        
        # El servicio se inicializará en el método initialize
        self.ingestion_service = None
        self._logger = logging.getLogger(f"{self.service_name}.IngestionWorker")
    
    async def initialize(self):
        """
        Inicializa el worker y sus dependencias.
        
        Crea la instancia de IngestionService con las conexiones necesarias.
        """
        # Primero llamar a la inicialización del BaseWorker
        await super().initialize()
        
        # Inicializar el servicio de ingestión
        self.ingestion_service = IngestionService(
            app_settings=self.app_settings,
            service_redis_client=self.redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        # Inicializar componentes del servicio
        await self.ingestion_service.initialize()
        
        self._logger.info(
            f"IngestionWorker {self.consumer_name} inicializado. "
            f"Escuchando en stream: {self.action_stream_name}, "
            f"grupo: {self.consumer_group_name}"
        )
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a IngestionService.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            Exception: Si hay un error en el procesamiento
        """
        if not self.ingestion_service:
            raise RuntimeError("IngestionService no está inicializado")
        
        # Registrar recepción de la acción
        self._logger.info(
            f"Procesando acción: {action.action_type} "
            f"(task_id: {action.task_id}, tenant_id: {action.tenant_id})"
        )
        
        try:
            # Delegar al servicio
            result = await self.ingestion_service.process_action(action)
            
            if result:
                self._logger.info(
                    f"Acción {action.action_type} procesada exitosamente"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error procesando acción {action.action_type}: {e}",
                exc_info=True,
                extra=action.get_log_extra() if hasattr(action, 'get_log_extra') else {}
            )
            raise
            
    async def stop(self):
        """
        Detiene el worker de manera ordenada.
        """
        self._logger.info(f"Deteniendo IngestionWorker {self.consumer_name}")
        await super().stop()
