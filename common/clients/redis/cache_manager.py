"""
Este módulo proporciona una clase para gestionar el ciclo de vida completo de la caché en Redis.

Clases:
- CacheManager: Gestiona la generación de claves, carga, guardado y TTL de la caché.
"""

import logging
from typing import Type, TypeVar, Optional, Union, List, Generic, Any
import uuid

import redis.asyncio as redis_async
from pydantic import BaseModel

from common.config.base_settings import CommonAppSettings
from .cache_key_manager import CacheKeyManager
from .redis_state_manager import RedisStateManager

# Tipo genérico para el modelo de estado Pydantic
TStateModel = TypeVar('TStateModel', bound=BaseModel)

logger = logging.getLogger(__name__)

class CacheManager(Generic[TStateModel]):
    """
    Gestor de caché que combina generación de claves y persistencia.
    
    Proporciona métodos genéricos para cualquier tipo de caché con
    claves estandarizadas y validación Pydantic.
    """
    
    def __init__(
        self,
        redis_conn: redis_async.Redis,
        state_model: Type[TStateModel],
        app_settings: CommonAppSettings,
        default_ttl: Optional[int] = None
    ):
        """
        Inicializa el CacheManager.
        
        Args:
            redis_conn: Conexión a Redis
            state_model: Modelo Pydantic para validación del estado
            app_settings: Configuración de la aplicación
            default_ttl: TTL por defecto en segundos (opcional)
        """
        self.key_manager = CacheKeyManager(
            environment=app_settings.environment,
            service_name=app_settings.service_name
        )
        self.state_manager = RedisStateManager[state_model](
            redis_conn=redis_conn,
            state_model=state_model,
            app_settings=app_settings,
            cache_key_manager=self.key_manager
        )
        self.default_ttl = default_ttl
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.debug(f"CacheManager para el modelo {state_model.__name__} inicializado.")
    
    # Métodos genéricos para cualquier tipo de caché
    
    async def get(self, cache_type: str, context: Union[str, List[str]]) -> Optional[TStateModel]:
        """
        Obtiene un objeto de la caché usando un tipo y contexto específicos.
        
        Args:
            cache_type: Tipo de caché (ej: "history", "config", "embedding")
            context: Contexto específico (string o lista de strings)
            
        Returns:
            El objeto si existe, None en caso contrario
        """
        cache_key = self.key_manager.get_cache_key(cache_type, context)
        
        self.logger.debug(
            "Recuperando objeto desde caché",
            extra={
                "cache_key": cache_key,
                "cache_type": cache_type,
                "context": context
            }
        )
        
        return await self.state_manager.load_state(cache_key)
    
    async def save(
        self, 
        cache_type: str, 
        context: Union[str, List[str]], 
        data: TStateModel, 
        ttl: Optional[int] = None
    ) -> None:
        """
        Guarda un objeto en la caché usando un tipo y contexto específicos.
        
        Args:
            cache_type: Tipo de caché (ej: "history", "config", "embedding")
            context: Contexto específico (string o lista de strings)
            data: El objeto a guardar
            ttl: Tiempo de vida en segundos (opcional, usa default_ttl si no se proporciona)
        """
        cache_key = self.key_manager.get_cache_key(cache_type, context)
        expiration = ttl if ttl is not None else self.default_ttl
        
        self.logger.debug(
            "Guardando objeto en caché",
            extra={
                "cache_key": cache_key,
                "cache_type": cache_type,
                "context": context,
                "ttl_seconds": expiration
            }
        )
        
        await self.state_manager.save_state(cache_key, data, expiration_seconds=expiration)
    
    async def delete(self, cache_type: str, context: Union[str, List[str]]) -> bool:
        """
        Elimina un objeto de la caché usando un tipo y contexto específicos.
        
        Args:
            cache_type: Tipo de caché (ej: "history", "config", "embedding")
            context: Contexto específico (string o lista de strings)
            
        Returns:
            True si se eliminó, False si no existía
        """
        cache_key = self.key_manager.get_cache_key(cache_type, context)
        
        self.logger.debug(
            "Eliminando objeto de caché",
            extra={
                "cache_key": cache_key,
                "cache_type": cache_type,
                "context": context
            }
        )
        
        return await self.state_manager.delete_state(cache_key)
