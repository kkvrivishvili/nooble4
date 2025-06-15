import logging
from abc import ABC
from typing import Optional

from redis.asyncio import Redis as AIORedis
from common.config.base_settings import CommonAppSettings


class BaseHandler(ABC):
    """
    Clase base abstracta y mínima para Handlers de utilidad de dominio.

    Los Handlers son componentes que encapsulan lógica de negocio específica
    o interacciones con otros sistemas (ej. una API externa, una base de datos específica)
    y son utilizados por la Capa de Servicio para mantener su código limpio y organizado.

    Esta clase base proporciona un logger configurado y acceso a la configuración
    de la aplicación.
    """
    def __init__(
        self,
        app_settings: CommonAppSettings,
        # Opcional: pasar una conexión Redis directa si el handler la necesita.
        # Es preferible que el Service gestione las interacciones Redis principales,
        # pero algunos handlers podrían necesitar acceso directo para tareas muy específicas.
        direct_redis_conn: Optional[AIORedis] = None,
        # Opcional: pasar el nombre del servicio padre si se necesita para logging más específico
        # o si app_settings no está disponible en el contexto de creación.
        # Sin embargo, app_settings.service_name es preferible.
        # parent_service_name: Optional[str] = None 
    ):
        """
        Inicializa el handler base.

        Args:
            app_settings: La configuración de la aplicación.
            direct_redis_conn: (Opcional) Una conexión Redis asíncrona directa.
        """
        if not app_settings.service_name:
            raise ValueError("CommonAppSettings debe tener 'service_name' configurado para el logger del handler.")

        self.app_settings = app_settings
        self.direct_redis_conn = direct_redis_conn
        # El logger se nombra usando el service_name de app_settings y el nombre de la clase del handler.
        self._logger = logging.getLogger(f"{app_settings.service_name}.{self.__class__.__name__}")
        self._logger.debug(f"Handler {self.__class__.__name__} inicializado.")

    # Los Handlers ya no tienen un método 'execute' abstracto ni una inicialización asíncrona compleja.
    # Si un handler necesita una inicialización asíncrona, puede implementar un método
    # `async def setup(self)` que el Service llamará explícitamente después de instanciarlo.
    # Los métodos de un handler serán específicos de su dominio y llamados directamente por el Service.

