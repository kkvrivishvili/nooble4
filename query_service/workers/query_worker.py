"""
Worker principal del Query Service.

Implementa BaseWorker para consumir DomainActions del stream Redis
y delegar el procesamiento al QueryService.
"""

import logging
from typing import Optional, Dict, Any

from common.workers import BaseWorker
from common.models import DomainAction
from common.clients import BaseRedisClient

from ..services.query_service import QueryService
from common.config.service_settings.query import QueryServiceSettings


class QueryWorker(BaseWorker):
    """
    Worker que procesa acciones de consulta desde Redis Streams.
    
    Consume DomainActions del stream del Query Service y las
    procesa usando QueryService (que implementa BaseService).
    """
    
    def __init__(
        self, 
        app_settings=None,
        async_redis_conn=None,
        consumer_id_suffix: Optional[str] = None
    ):
        """
        Inicializa el QueryWorker.
        
        Args:
            app_settings: QueryServiceSettings (si no se proporciona, se carga)
            async_redis_conn: Conexión Redis asíncrona
            consumer_id_suffix: Sufijo para el ID del consumidor
        """
        # Cargar settings si no se proporcionan
        if app_settings is None:
            app_settings = QueryServiceSettings()
        
        if async_redis_conn is None:
            raise ValueError("async_redis_conn es requerido para QueryWorker")
        
        # Inicializar BaseWorker
        super().__init__(
            app_settings=app_settings,
            async_redis_conn=async_redis_conn,
            consumer_id_suffix=consumer_id_suffix
        )
        
        # El servicio se inicializará en el método initialize
        self.query_service = None
        
        self._logger = logging.getLogger(f"{__name__}.{self.consumer_name}")
        
    async def initialize(self):
        """
        Inicializa el worker y sus dependencias.
        
        Crea la instancia de QueryService con las conexiones necesarias.
        """
        # Primero llamar a la inicialización del BaseWorker
        await super().initialize()
        
        # Crear cliente Redis para que el servicio pueda enviar acciones
        service_redis_client = BaseRedisClient(
            service_name=self.service_name,
            redis_client=self.async_redis_conn,
            settings=self.app_settings
        )
        
        # Inicializar QueryService
        self.query_service = QueryService(
            app_settings=self.app_settings,
            service_redis_client=service_redis_client,
            direct_redis_conn=self.async_redis_conn
        )
        
        self._logger.info(
            f"QueryWorker inicializado. "
            f"Escuchando en stream: {self.action_stream_name}, "
            f"grupo: {self.consumer_group_name}"
        )
    
    async def _handle_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction delegando a QueryService.
        
        Args:
            action: La acción a procesar
            
        Returns:
            Diccionario con los datos de respuesta o None
            
        Raises:
            Exception: Si hay un error en el procesamiento
        """
        if not self.query_service:
            raise RuntimeError("QueryService no inicializado. Llamar initialize() primero.")
        
        self._logger.debug(
            f"Procesando acción {action.action_type} "
            f"(ID: {action.action_id}, Tenant: {action.tenant_id})"
        )
        
        # Delegar al servicio
        try:
            result = await self.query_service.process_action(action)
            
            # Log resultado
            if result:
                self._logger.debug(
                    f"Acción {action.action_id} procesada exitosamente. "
                    f"Respuesta generada: {bool(result)}"
                )
            else:
                self._logger.debug(
                    f"Acción {action.action_id} procesada sin respuesta (fire-and-forget)"
                )
            
            return result
            
        except Exception as e:
            self._logger.error(
                f"Error procesando acción {action.action_id}: {e}",
                exc_info=True
            )
            # Re-lanzar para que BaseWorker maneje el error
            raise