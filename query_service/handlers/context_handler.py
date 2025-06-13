"""
Context Handler - Manejo y validación de contextos de consulta en Query Service.

Este módulo se encarga de:
- Resolver ExecutionContext desde DomainActions
- Gestionar configuraciones de RAG
- Cache de configuraciones de colecciones
"""

import logging
from typing import Optional, Dict, Any
import json

from common.models.execution_context import ExecutionContext
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QueryContextHandler:
    """
    Manejador de contextos de consulta para Query Service.
    
    Responsable de resolver y validar contextos para consultas RAG
    y búsquedas vectoriales.
    """
    
    def __init__(self, redis_client=None, supabase_client=None):
        """
        Inicializa handler.
        
        Args:
            redis_client: Cliente Redis para cache (opcional)
            supabase_client: Cliente Supabase para collections (opcional)
        """
        self.redis = redis_client
        self.supabase = supabase_client
        
        # Cache TTL para configuraciones de colecciones (10 minutos)
        self.collection_config_cache_ttl = 600
    
    async def resolve_query_context(
        self,
        context_dict: Dict[str, Any]
    ) -> ExecutionContext:
        """
        Resuelve ExecutionContext desde diccionario.
        
        Args:
            context_dict: Diccionario con datos del contexto
            
        Returns:
            ExecutionContext válido
            
        Raises:
            ValueError: Si el contexto no es válido
        """
        try:
            # Crear ExecutionContext desde diccionario
            context = ExecutionContext.from_dict(context_dict)
            
            logger.info(f"Contexto de consulta resuelto: {context.context_id}")
            return context
            
        except Exception as e:
            logger.error(f"Error resolviendo contexto de consulta: {str(e)}")
            raise ValueError(f"Contexto de consulta inválido: {str(e)}")
    
    async def get_collection_configuration(
        self,
        collection_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Obtiene configuración de colección (con cache).
        
        Args:
            collection_id: ID de la colección
            tenant_id: ID del tenant
            
        Returns:
            Dict con configuración de la colección
            
        Raises:
            ValueError: Si la colección no existe o no es accesible
        """
        # Cache key
        cache_key = f"collection_config:{tenant_id}:{collection_id}"
        
        # Verificar cache
        if self.redis:
            cached_config = await self.redis.get(cache_key)
            if cached_config:
                try:
                    return json.loads(cached_config)
                except json.JSONDecodeError:
                    logger.warning(f"Config en cache inválida para collection {collection_id}")
        
        # Obtener desde base de datos
        collection_config = await self._fetch_collection_from_db(collection_id, tenant_id)
        
        if not collection_config:
            raise ValueError(f"Colección {collection_id} no encontrada para tenant {tenant_id}")
        
        # Cachear configuración
        if self.redis:
            await self.redis.setex(
                cache_key, 
                self.collection_config_cache_ttl, 
                json.dumps(collection_config)
            )
        
        logger.info(f"Configuración de colección obtenida: {collection_id}")
        return collection_config
    
    async def validate_query_permissions(
        self,
        context: ExecutionContext,
        collection_config: Dict[str, Any],
        query_type: str = "generate"
    ) -> bool:
        """
        Valida permisos de consulta.
        
        Args:
            context: Contexto de ejecución
            collection_config: Configuración de la colección
            query_type: Tipo de consulta (generate, search)
            
        Returns:
            True si tiene permisos
            
        Raises:
            ValueError: Si no tiene permisos
        """
        # Validar que la colección esté activa
        if not collection_config.get("is_active", True):
            raise ValueError(f"Colección {collection_config.get('id')} está desactivada")
        
        logger.info(f"Permisos de consulta validados para {context.context_id}")
        return True
    
    async def _fetch_collection_from_db(self, collection_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene configuración de colección desde base de datos.
        
        TODO: Implementar lookup real cuando esté disponible.
        """
        if not self.supabase:
            # Sin DB configurada, simular configuración básica
            logger.warning("Sin DB configurada para collections")
            return {
                "id": collection_id,
                "tenant_id": tenant_id,
                "name": f"Collection {collection_id}",
                "is_active": True,
                "vector_dimensions": 1536,
                "similarity_metric": "cosine"
            }
        
        try:
            # Simulación temporal
            logger.info(f"Simulando fetch de collection: {collection_id} para tenant {tenant_id}")
            return {
                "id": collection_id,
                "tenant_id": tenant_id,
                "name": f"Collection {collection_id}",
                "is_active": True,
                "vector_dimensions": 1536,
                "similarity_metric": "cosine",
                "document_count": 1000
            }
            
        except Exception as e:
            logger.error(f"Error en lookup de collection: {str(e)}")
            return None
    
    async def invalidate_collection_cache(self, collection_id: str, tenant_id: str):
        """Invalida cache de configuración de colección."""
        if self.redis:
            cache_key = f"collection_config:{tenant_id}:{collection_id}"
            await self.redis.delete(cache_key)
            logger.info(f"Cache invalidado para collection {collection_id}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        if not self.redis:
            return {"cache": "disabled"}
        
        # Contar keys de configuración de colecciones
        config_keys = await self.redis.keys("collection_config:*")
        
        return {
            "cache": "enabled",
            "collection_configs": len(config_keys),
            "ttl_seconds": self.collection_config_cache_ttl
        }


# Factory function
async def get_query_context_handler(redis_client=None, supabase_client=None) -> QueryContextHandler:
    """Factory para obtener QueryContextHandler configurado."""
    return QueryContextHandler(redis_client, supabase_client)