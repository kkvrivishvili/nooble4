import logging
from typing import Type, Optional, Generic, TypeVar

import redis.asyncio as redis_async
from pydantic import BaseModel, ValidationError

from common.config.base_settings import CommonAppSettings

# Importación condicional para evitar dependencias circulares
# Solo se usa para type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .cache_key_manager import CacheKeyManager

# Tipo genérico para el modelo de estado Pydantic
TStateModel = TypeVar('TStateModel', bound=BaseModel)

class RedisStateManager(Generic[TStateModel]):
    """
    Gestiona la persistencia de un objeto de estado (un modelo Pydantic) en Redis.

    Proporciona métodos para cargar, guardar y eliminar el estado, manejando la
    serialización/deserialización JSON y la validación Pydantic.

    Esta clase es genérica y puede ser utilizada con cualquier modelo Pydantic.
    """

    def __init__(
        self,
        redis_conn: redis_async.Redis,
        state_model: Type[TStateModel],
        app_settings: CommonAppSettings,
        # Opcional: un gestor de claves de caché para generar claves estandarizadas
        cache_key_manager: Optional['CacheKeyManager'] = None
    ):
        """
        Inicializa el RedisStateManager.

        Args:
            redis_conn: Una conexión Redis asíncrona (instancia de redis.asyncio.Redis).
            state_model: El modelo Pydantic que representa la estructura del estado.
            app_settings: La configuración de la aplicación (para el logger y service_name).
        """
        if not app_settings.service_name:
            raise ValueError("CommonAppSettings debe tener 'service_name' configurado.")

        self.redis_conn = redis_conn
        self.state_model = state_model
        self.app_settings = app_settings
        self.cache_key_manager = cache_key_manager
        self._logger = logging.getLogger(f"{app_settings.service_name}.RedisStateManager.{state_model.__name__}")
        self._logger.debug(f"RedisStateManager para el modelo {state_model.__name__} inicializado.")

    async def load_state(self, state_key: str) -> Optional[TStateModel]:
        """
        Carga y deserializa el estado desde Redis usando la clave proporcionada.

        Args:
            state_key: La clave única de Redis bajo la cual se almacena el estado.

        Returns:
            Una instancia del state_model si se encuentra y valida, o None.
            
        Raises:
            redis_async.RedisError: Si hay un error de comunicación con Redis.
            ValidationError: Si los datos en Redis no se pueden validar contra el state_model.
        """
        # full_key = f"{self.key_prefix}:{state_key}" if self.key_prefix else state_key
        self._logger.debug(f"Cargando estado desde la clave: {state_key}")
        try:
            state_data_bytes = await self.redis_conn.get(state_key)
            
            if not state_data_bytes:
                self._logger.debug(f"No se encontró estado para la clave: {state_key}")
                return None
            
            state_data_str = state_data_bytes.decode('utf-8') if isinstance(state_data_bytes, bytes) else state_data_bytes
            # model_validate_json es el método correcto en Pydantic v2
            return self.state_model.model_validate_json(state_data_str)
        except redis_async.RedisError as e:
            self._logger.error(f"Error de Redis al cargar estado desde '{state_key}': {e}", exc_info=True)
            raise
        except ValidationError as e:
            self._logger.error(f"Error de validación al deserializar estado desde '{state_key}': {e}", exc_info=True)
            raise
        except Exception as e:
            self._logger.error(f"Error inesperado al cargar estado desde '{state_key}': {e}", exc_info=True)
            raise

    async def save_state(self, state_key: str, state_data: TStateModel, expiration_seconds: Optional[int] = None):
        """
        Guarda el objeto de estado en Redis bajo la clave proporcionada.

        Args:
            state_key: La clave única de Redis bajo la cual se guardará el estado.
            state_data: La instancia del state_model a guardar. No debe ser None.
            expiration_seconds: (Opcional) Tiempo en segundos para la expiración de la clave.

        Raises:
            TypeError: Si state_data es None.
            redis_async.RedisError: Si hay un error de comunicación con Redis.
        """
        if state_data is None:
            # Para borrar, usar delete_state explícitamente.
            # Esto previene borrados accidentales si se pasa None por error.
            raise TypeError("state_data no puede ser None para save_state. Use delete_state para eliminar.")

        # full_key = f"{self.key_prefix}:{state_key}" if self.key_prefix else state_key
        self._logger.debug(f"Guardando estado en la clave: {state_key} con expiración: {expiration_seconds}s")
        try:
            # model_dump_json es el método correcto en Pydantic v2
            await self.redis_conn.set(state_key, state_data.model_dump_json(), ex=expiration_seconds)
        except redis_async.RedisError as e:
            self._logger.error(f"Error de Redis al guardar estado en '{state_key}': {e}", exc_info=True)
            raise
        except Exception as e:
            self._logger.error(f"Error inesperado al guardar estado en '{state_key}': {e}", exc_info=True)
            raise

    async def delete_state(self, state_key: str) -> bool:
        """
        Elimina el estado de Redis bajo la clave proporcionada.

        Args:
            state_key: La clave única de Redis para el estado a eliminar.

        Returns:
            True si la clave fue eliminada, False si la clave no existía.
            
        Raises:
            redis_async.RedisError: Si hay un error de comunicación con Redis.
        """
        # full_key = f"{self.key_prefix}:{state_key}" if self.key_prefix else state_key
        self._logger.debug(f"Eliminando estado de la clave: {state_key}")
        try:
            result = await self.redis_conn.delete(state_key)
            return result > 0 # delete devuelve el número de claves eliminadas
        except redis_async.RedisError as e:
            self._logger.error(f"Error de Redis al eliminar estado de '{state_key}': {e}", exc_info=True)
            raise
        except Exception as e:
            self._logger.error(f"Error inesperado al eliminar estado de '{state_key}': {e}", exc_info=True)
            raise
