"""
Worker principal del Embedding Service.

Implementa BaseWorker para consumir DomainActions del stream Redis
y delegar el procesamiento al EmbeddingService.
"""

import logging
from typing import Optional, Dict, Any

from common.workers import BaseWorker
from common.models import DomainAction
from common.clients import BaseRedisClient

from ..services.embedding_service import EmbeddingService
from ..config.settings import get_settings


class EmbeddingWorker(BaseWorker):
    """
    Worker que procesa acciones de embedding desde Redis Streams.
    
    Consume DomainActions del stream del Embedding Service y las
    procesa usando EmbeddingService (que implementa BaseService).
    """
    
    def __init__(
        self, 
        app_settings=None,
        async_redis_conn=None,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el EmbeddingWorker.
        
        Args:
            app_settings: EmbeddingServiceSettings (si no se proporciona, se carga)
            async_redis_conn: Conexión Redis asíncrona
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        # Cargar settings si no se proporcionan
        if app_settings is None:
            app_settings = get_settings()
        
        if async_redis_conn is None:
            raise ValueError("async_redis_conn es requerido para EmbeddingWorker")
        
        # Inicializar BaseWorker
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn,
            consumer_id_suffix=consumer_id_suffix
        )
        
        # El servicio se inicializará en el método initialize
        self.embedding_service = None
        
        self.logger = logging.getLogger(f"{__name__}.{self.consumer_name}")
        
    async def initialize(self):
        """
        Inicializa el worker y sus dependencias.
        
        Crea la instancia de EmbeddingService con las conexiones necesarias.
        """
        # Primero llamar a la inicialización del BaseWorker
        await super().initialize()
        
        # Crear cliente Redis para que el servicio pueda enviar acciones
        service_redis_client = BaseRedisClient(
            service_name=self.service_name,
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )
        
        # Inicializar EmbeddingService
        self.embedding_service = EmbeddingService(
            app_settings=self.app_settings,
            service_redis_client=service_redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        self.logger.info(
            f"EmbeddingWorker inicializado. "
            f"Escuchando en stream: {self.action_stream_name}, "
            f"grupo: {self.consumer_group_name}"
        )
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a EmbeddingService.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            Exception: Si hay un error en el procesamiento
        """
        if not self.embedding_service:
            raise RuntimeError("EmbeddingService no inicializado. Llamar initialize() primero.")
        
        self.logger.debug(
            f"Procesando acción {action.action_type} "
            f"(ID: {action.action_id}, Tenant: {action.tenant_id})"
        )
        
        # Delegar al servicio
        try:
            result = await self.embedding_service.process_action(action)
            
            # Log resultado
            if result:
                self.logger.debug(
                    f"Acción {action.action_id} procesada exitosamente. "
                    f"Respuesta generada: {bool(result)}"
                )
            else:
                self.logger.debug(
                    f"Acción {action.action_id} procesada sin respuesta (fire-and-forget)"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Error procesando acción {action.action_id}: {e}",
                exc_info=True
            )
            # Re-lanzar para que BaseWorker maneje el error
            raise