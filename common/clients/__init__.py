"""Módulo de clientes comunes.

Este módulo exporta los clientes comunes utilizados para la comunicación entre servicios.
"""

from .base_redis_client import BaseRedisClient

__all__ = ["BaseRedisClient"]
