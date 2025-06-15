import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from redis.asyncio import Redis as AIORedis

from common.config.base_settings import CommonAppSettings
from common.models.actions import DomainAction
from common.clients import BaseRedisClient # Importar BaseRedisClient


class BaseService(ABC):
    """
    Clase base abstracta para la Capa de Servicio.

    Define el contrato que todas las clases de servicio deben seguir.
    Actúa como un orquestador de la lógica de negocio, utilizando
    componentes especializados (Handlers) para realizar tareas específicas.

    Esta clase es agnóstica a la infraestructura de workers y colas, 
    pero define el punto de entrada principal (`process_action`) desde el Worker.
    """

    def __init__(
        self,
        app_settings: CommonAppSettings,
        service_redis_client: Optional[BaseRedisClient] = None,
        direct_redis_conn: Optional[AIORedis] = None,
    ):
        """
        Inicializa el servicio base con dependencias comunes.

        Args:
            app_settings: La configuración de la aplicación (contiene service_name, environment, etc.).
            service_redis_client: (Opcional) Una instancia de BaseRedisClient 
                                    para que el servicio pueda iniciar nuevas acciones 
                                    hacia otros servicios.
            direct_redis_conn: (Opcional) Una conexión Redis asíncrona directa si el 
                               servicio la necesita para operaciones que no son 
                               DomainActions (ej. contadores, locks simples).
        """
        if not app_settings.service_name:
            raise ValueError("CommonAppSettings debe tener 'service_name' configurado.")
            
        self.app_settings = app_settings
        self.service_name = app_settings.service_name
        self.service_redis_client = service_redis_client
        self.direct_redis_conn = direct_redis_conn
        self._logger = logging.getLogger(f"{self.service_name}.{self.__class__.__name__}")
        self._logger.info(f"Servicio {self.__class__.__name__} inicializado para {self.service_name}")

    @abstractmethod
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """
        Procesa una DomainAction y retorna un diccionario con los datos para la 
        DomainActionResponse (en caso de pseudo-síncrono) o para la 
        DomainAction de callback (en caso de asíncrono con callback).
        
        Si la acción es puramente asíncrona (fire-and-forget) y no requiere 
        respuesta ni callback, o si el BaseWorker maneja la respuesta de error 
        automáticamente, este método puede retornar None.

        Este es el punto de entrada principal para la lógica de negocio, 
        llamado por el BaseWorker.

        Args:
            action: La DomainAction recibida por el worker.

        Returns:
            Un diccionario con los datos para la respuesta/callback, o None.
            Ejemplo para respuesta: {"field1": "value1", "field2": 123}
            Ejemplo para callback: {"status": "completed", "item_id": action.data.get("item_id")}
        """
        pass

