"""
Pool de conexiones Redis compartido.
"""

import logging
import redis.asyncio as redis
from typing import Optional

from refactorizado.common.config.base_settings import CommonAppSettings # Added import

logger = logging.getLogger(__name__)

class RedisPool:
    """Gestor singleton de conexiones Redis."""
    
    _instance: Optional['RedisPool'] = None
    _redis_client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self, settings: CommonAppSettings) -> redis.Redis: # Changed signature
        """
        Obtiene el cliente Redis compartido.
        
        Returns:
            Cliente Redis conectado
        """
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                settings.redis_url, # Use settings
                decode_responses=settings.redis_decode_responses, # Use settings
                socket_connect_timeout=settings.redis_socket_connect_timeout, # Use settings
                socket_keepalive=True, # Kept hardcoded for now
                socket_keepalive_options={}, # Kept hardcoded for now
                max_connections=settings.redis_max_connections, # Use settings
                health_check_interval=settings.redis_health_check_interval # Use settings
            )
            
            try:
                await self._redis_client.ping()
                logger.info("Pool de Redis inicializado exitosamente")
            except Exception as e:
                logger.error(f"Error conectando a Redis: {str(e)}")
                self._redis_client = None
                raise
        
        return self._redis_client
    
    async def close(self):
        """Cierra el pool de conexiones."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            logger.info("Pool de Redis cerrado")

# Instancia global
redis_pool = RedisPool()

async def get_redis_client(settings: CommonAppSettings) -> redis.Redis: # Changed signature
    """Helper para obtener cliente Redis."""
    return await redis_pool.get_client(settings) # Pass settings

async def close_redis_pool():
    """Helper para cerrar pool."""
    await redis_pool.close()
