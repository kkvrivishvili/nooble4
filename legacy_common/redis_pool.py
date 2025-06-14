"""
Pool de conexiones Redis compartido.
"""

import logging
import redis.asyncio as redis
from typing import Optional

logger = logging.getLogger(__name__)

class RedisPool:
    """Gestor singleton de conexiones Redis."""
    
    _instance: Optional['RedisPool'] = None
    _redis_client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self, redis_url: str = "redis://localhost:6379") -> redis.Redis:
        """
        Obtiene el cliente Redis compartido.
        
        Returns:
            Cliente Redis conectado
        """
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                max_connections=50,
                health_check_interval=30
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

async def get_redis_client(redis_url: str = "redis://localhost:6379") -> redis.Redis:
    """Helper para obtener cliente Redis."""
    return await redis_pool.get_client(redis_url)

async def close_redis_pool():
    """Helper para cerrar pool."""
    await redis_pool.close()
