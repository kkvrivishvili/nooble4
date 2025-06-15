"""
Gestor de conexiones Redis centralizado.
"""

import logging
import redis.asyncio as redis
from typing import Optional, Dict, Union

from common.config.base_settings import CommonAppSettings

logger = logging.getLogger(__name__)

class RedisManager:
    """Gestor de conexiones Redis para la aplicación."""

    def __init__(self, settings: CommonAppSettings):
        """
        Inicializa el RedisManager con la configuración proporcionada.

        Args:
            settings: La configuración común de la aplicación.
        """
        self._settings = settings
        self._redis_client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """
        Obtiene el cliente Redis asíncrono.

        Si el cliente no está inicializado, lo crea y lo configura.
        Realiza un ping para asegurar la conectividad en la primera conexión.

        Returns:
            Una instancia del cliente Redis (redis.asyncio.Redis).
        
        Raises:
            Exception: Si falla la conexión o el ping a Redis.
        """
        if self._redis_client is None:
            logger.info(f"Inicializando cliente Redis con URL: {self._settings.redis_url}")
            try:
                self._redis_client = redis.from_url(
                    self._settings.redis_url,
                    decode_responses=self._settings.redis_decode_responses,
                    socket_connect_timeout=self._settings.redis_socket_connect_timeout,
                    socket_keepalive=self._settings.redis_socket_keepalive,
                    socket_keepalive_options=self._settings.redis_socket_keepalive_options,
                    max_connections=self._settings.redis_max_connections,
                    health_check_interval=self._settings.redis_health_check_interval
                )
                await self._redis_client.ping()
                logger.info("Cliente Redis conectado y ping exitoso.")
            except Exception as e:
                logger.error(f"Error al conectar o hacer ping a Redis: {e}")
                self._redis_client = None # Asegurar que no se reintente con un cliente fallido
                raise
        
        if self._redis_client is None: # Doble chequeo por si falló la inicialización
             raise ConnectionError("No se pudo establecer la conexión con Redis.")

        return self._redis_client

    async def close(self):
        """
        Cierra el cliente Redis y el pool de conexiones asociado, si está inicializado.
        """
        if self._redis_client:
            logger.info("Cerrando cliente Redis...")
            await self._redis_client.close()
            self._redis_client = None
            logger.info("Cliente Redis cerrado exitosamente.")
        else:
            logger.info("El cliente Redis no estaba inicializado, no se requiere cierre.")
