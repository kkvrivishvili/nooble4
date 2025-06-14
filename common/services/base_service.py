from abc import ABC
from typing import Optional

from redis.asyncio import Redis as AIORedis

from common.config.base_settings import CommonAppSettings


class BaseService(ABC):
    """
    Clase base abstracta para la Capa de Servicio.

    Define el contrato que todas las clases de servicio deben seguir.
    Actúa como un orquestador de la lógica de negocio, utilizando
    componentes especializados (Handlers) para realizar tareas específicas.

    Esta clase es agnóstica a la infraestructura de workers y colas.
    """

    def __init__(
        self,
        app_settings: CommonAppSettings,
        redis_client: Optional[AIORedis] = None,
    ):
        """
        Inicializa el servicio base con dependencias comunes.

        Args:
            app_settings: La configuración de la aplicación.
            redis_client: Un cliente de Redis asíncrono opcional.
        """
        self.app_settings = app_settings
        self.redis_client = redis_client

    # No se definen métodos abstractos aquí porque los métodos de la capa de
    # servicio son específicos del dominio de cada microservicio.
    # La herencia de esta clase es el contrato principal.
