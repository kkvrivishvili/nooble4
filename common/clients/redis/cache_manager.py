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

class CacheManager(Generic[TStateModel]):
    """
    Gestiona el ciclo de vida completo de la caché en Redis.
    
    Combina la generación de claves estandarizadas con la carga/guardado de estado.
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
            redis_conn: Una conexión Redis asíncrona.
            state_model: El modelo Pydantic que representa la estructura del estado.
            app_settings: La configuración de la aplicación.
            default_ttl: Tiempo de vida predeterminado en segundos para las entradas de caché.
        """
        if not app_settings.service_name:
            raise ValueError("CommonAppSettings debe tener 'service_name' configurado.")
        
        self.app_settings = app_settings
        self.default_ttl = default_ttl
        
        # Inicializar el generador de claves
        self.key_manager = CacheKeyManager(
            environment=app_settings.environment,
            service_name=app_settings.service_name
        )
        
        # Inicializar el gestor de estado
        self.state_manager = RedisStateManager[state_model](
            redis_conn=redis_conn,
            state_model=state_model,
            app_settings=app_settings,
            cache_key_manager=self.key_manager
        )
        
        self._logger = logging.getLogger(f"{app_settings.service_name}.CacheManager.{state_model.__name__}")
        self._logger.debug(f"CacheManager para el modelo {state_model.__name__} inicializado.")
    
    # Métodos para historial de conversación
    
    async def get_history(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> Optional[TStateModel]:
        """
        Obtiene el historial de conversación de la caché.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            
        Returns:
            El historial de conversación o None si no existe
        """
        cache_key = self.key_manager.get_history_key(tenant_id, session_id)
        return await self.state_manager.load_state(cache_key)
    
    async def save_history(
        self, 
        tenant_id: uuid.UUID, 
        session_id: uuid.UUID, 
        history: TStateModel, 
        ttl: Optional[int] = None
    ) -> None:
        """
        Guarda el historial de conversación en la caché.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            history: El historial a guardar
            ttl: Tiempo de vida en segundos (opcional, usa default_ttl si no se proporciona)
        """
        cache_key = self.key_manager.get_history_key(tenant_id, session_id)
        expiration = ttl if ttl is not None else self.default_ttl
        await self.state_manager.save_state(cache_key, history, expiration_seconds=expiration)
    
    async def delete_history(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        """
        Elimina el historial de conversación de la caché.
        
        Args:
            tenant_id: ID del inquilino
            session_id: ID de la sesión
            
        Returns:
            True si se eliminó, False si no existía
        """
        cache_key = self.key_manager.get_history_key(tenant_id, session_id)
        return await self.state_manager.delete_state(cache_key)
    
    # Métodos para configuraciones
    
    async def get_config(self, entity_id: uuid.UUID, config_type: str) -> Optional[TStateModel]:
        """
        Obtiene una configuración de la caché.
        
        Args:
            entity_id: ID de la entidad (usuario, agente, etc.)
            config_type: Tipo de configuración (user, agent, etc.)
            
        Returns:
            La configuración o None si no existe
        """
        cache_key = self.key_manager.get_config_key(entity_id, config_type)
        return await self.state_manager.load_state(cache_key)
    
    async def save_config(
        self, 
        entity_id: uuid.UUID, 
        config_type: str, 
        config: TStateModel, 
        ttl: Optional[int] = None
    ) -> None:
        """
        Guarda una configuración en la caché.
        
        Args:
            entity_id: ID de la entidad (usuario, agente, etc.)
            config_type: Tipo de configuración (user, agent, etc.)
            config: La configuración a guardar
            ttl: Tiempo de vida en segundos (opcional, usa default_ttl si no se proporciona)
        """
        cache_key = self.key_manager.get_config_key(entity_id, config_type)
        expiration = ttl if ttl is not None else self.default_ttl
        await self.state_manager.save_state(cache_key, config, expiration_seconds=expiration)
    
    # Métodos genéricos
    
    async def get(self, cache_type: str, context: Union[str, List[str]]) -> Optional[TStateModel]:
        """
        Obtiene un objeto de la caché usando un tipo y contexto personalizados.
        
        Args:
            cache_type: Tipo de caché personalizado
            context: Contexto específico (string o lista de strings)
            
        Returns:
            El objeto o None si no existe
        """
        cache_key = self.key_manager.get_custom_key(cache_type, context)
        return await self.state_manager.load_state(cache_key)
    
    async def save(
        self, 
        cache_type: str, 
        context: Union[str, List[str]], 
        data: TStateModel, 
        ttl: Optional[int] = None
    ) -> None:
        """
        Guarda un objeto en la caché usando un tipo y contexto personalizados.
        
        Args:
            cache_type: Tipo de caché personalizado
            context: Contexto específico (string o lista de strings)
            data: El objeto a guardar
            ttl: Tiempo de vida en segundos (opcional, usa default_ttl si no se proporciona)
        """
        cache_key = self.key_manager.get_custom_key(cache_type, context)
        expiration = ttl if ttl is not None else self.default_ttl
        await self.state_manager.save_state(cache_key, data, expiration_seconds=expiration)
    
    async def delete(self, cache_type: str, context: Union[str, List[str]]) -> bool:
        """
        Elimina un objeto de la caché usando un tipo y contexto personalizados.
        
        Args:
            cache_type: Tipo de caché personalizado
            context: Contexto específico (string o lista de strings)
            
        Returns:
            True si se eliminó, False si no existía
        """
        cache_key = self.key_manager.get_custom_key(cache_type, context)
        return await self.state_manager.delete_state(cache_key)
