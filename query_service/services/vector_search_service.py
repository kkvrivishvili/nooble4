"""
Vector Search Service - Servicio de búsqueda vectorial.

Maneja búsquedas en el vector store con cache y optimizaciones.
"""

import logging
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from common.services import BaseService
from query_service.clients.vector_store_client import VectorStoreClient
from query_service.config.settings import QuerySettings

logger = logging.getLogger(__name__)


class VectorSearchService(BaseService):
    """
    Servicio de búsqueda vectorial que hereda de BaseService.
    
    Proporciona búsqueda optimizada en vector stores
    con cache y métricas, utilizando dependencias inyectadas.
    """

    def __init__(self, app_settings: QuerySettings, redis_client=None):
        """
        Inicializa el servicio.

        Args:
            app_settings: Configuración de la aplicación (inyectada).
            redis_client: Cliente Redis para cache y métricas.
        """
        super().__init__(app_settings=app_settings, redis_client=redis_client)
        self.vector_store_client = VectorStoreClient()

        # Cache TTL para búsquedas (5 minutos)
        self.search_cache_ttl = self.app_settings.vector_search_cache_ttl or 300
    
    async def search_documents(
        self,
        collection_id: str,
        tenant_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca documentos similares en vector store.
        
        Args:
            collection_id: ID de la colección
            tenant_id: ID del tenant
            query_embedding: Vector de consulta
            top_k: Número máximo de resultados
            similarity_threshold: Umbral de similitud
            metadata_filter: Filtro por metadatos
            use_cache: Si usar cache de resultados
            
        Returns:
            Lista de documentos encontrados
        """
        start_time = time.time()
        
        try:
            # Generar cache key si se usa cache
            cache_key = None
            if use_cache and self.redis_client:
                cache_key = self._generate_search_cache_key(
                    collection_id, query_embedding, top_k, similarity_threshold
                )

                # Verificar cache
                cached_result = await self.redis_client.get(cache_key)
                if cached_result:
                    search_results = json.loads(cached_result)
                    logger.info(f"Búsqueda desde cache: {len(search_results)} docs")
                    await self._track_search_metrics(tenant_id, len(search_results), time.time() - start_time, True)
                    return search_results
            
            # Realizar búsqueda en vector store
            search_results = await self.vector_store_client.search_by_embedding(
                tenant_id=tenant_id,
                collection_id=collection_id,
                query_embedding=query_embedding,
                top_k=top_k,
                threshold=similarity_threshold,
                metadata_filter=metadata_filter
            )
            
            # Filtrar resultados por umbral
            filtered_results = [
                doc for doc in search_results 
                if doc.get("similarity", 0.0) >= similarity_threshold
            ]
            
            # Cachear resultado si es apropiado
            if use_cache and self.redis_client and cache_key and filtered_results:
                await self.redis_client.set(
                    cache_key,
                    json.dumps(filtered_results),
                    ex=self.search_cache_ttl,
                )
            
            search_time = time.time() - start_time
            logger.info(f"Búsqueda completada: {len(filtered_results)} docs en {search_time:.2f}s")
            
            # Tracking de métricas
            await self._track_search_metrics(tenant_id, len(filtered_results), search_time, False)
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {str(e)}")
            raise
    
    async def search_documents_bulk(
        self,
        searches: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Realiza múltiples búsquedas en lote.
        
        Args:
            searches: Lista de parámetros de búsqueda
            
        Returns:
            Lista de resultados por cada búsqueda
        """
        results = []
        
        for search_params in searches:
            try:
                search_result = await self.search_documents(**search_params)
                results.append(search_result)
            except Exception as e:
                logger.error(f"Error en búsqueda bulk: {str(e)}")
                results.append([])  # Resultado vacío en caso de error
        
        return results
    
    def _generate_search_cache_key(
        self,
        collection_id: str,
        query_embedding: List[float],
        top_k: int,
        similarity_threshold: float
    ) -> str:
        """Genera clave de cache para búsqueda."""
        import hashlib
        
        # Crear hash del embedding (tomar solo primeros 10 elementos para eficiencia)
        embedding_sample = str(query_embedding[:10])
        embedding_hash = hashlib.md5(embedding_sample.encode()).hexdigest()[:8]
        
        return f"search_cache:{collection_id}:{embedding_hash}:{top_k}:{similarity_threshold}"
    
    async def _track_search_metrics(
        self,
        tenant_id: str,
        results_count: int,
        search_time: float,
        from_cache: bool
    ):
        """Registra métricas de búsqueda."""
        if not self.redis:
            return
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"search_metrics:{tenant_id}:{today}"
            
            # Métricas básicas
            await self.redis.hincrby(metrics_key, "total_searches", 1)
            await self.redis.hincrby(metrics_key, "total_results", results_count)
            
            if from_cache:
                await self.redis.hincrby(metrics_key, "cache_hits", 1)
            else:
                await self.redis.hincrby(metrics_key, "cache_misses", 1)
            
            # Tiempo de búsqueda
            await self.redis.lpush(f"search_times:{tenant_id}", search_time)
            await self.redis.ltrim(f"search_times:{tenant_id}", 0, 999)  # Últimos 1000
            
            # TTL
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 días
            
        except Exception as e:
            logger.error(f"Error tracking search metrics: {str(e)}")
    
    async def get_search_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de búsqueda para un tenant."""
        if not self.redis:
            return {"metrics": "disabled"}
        
        try:
            today = datetime.now().date().isoformat()
            metrics_key = f"search_metrics:{tenant_id}:{today}"
            
            metrics = await self.redis.hgetall(metrics_key)
            
            # Obtener tiempos de búsqueda
            search_times = await self.redis.lrange(f"search_times:{tenant_id}", 0, -1)
            avg_search_time = 0.0
            if search_times:
                times = [float(t) for t in search_times]
                avg_search_time = sum(times) / len(times)
            
            # Calcular cache hit rate
            cache_hits = int(metrics.get("cache_hits", 0))
            cache_misses = int(metrics.get("cache_misses", 0))
            total_cache_requests = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0.0
            
            return {
                "date": today,
                "total_searches": int(metrics.get("total_searches", 0)),
                "total_results": int(metrics.get("total_results", 0)),
                "avg_results_per_search": self._calculate_avg_results(metrics),
                "avg_search_time": round(avg_search_time, 3),
                "cache_hit_rate": round(cache_hit_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo search stats: {str(e)}")
            return {"error": str(e)}
    
    def _calculate_avg_results(self, metrics: Dict[str, str]) -> float:
        """Calcula promedio de resultados por búsqueda."""
        total_searches = int(metrics.get("total_searches", 0))
        total_results = int(metrics.get("total_results", 0))
        
        if total_searches == 0:
            return 0.0
        
        return round(total_results / total_searches, 2)
    
    async def invalidate_search_cache(self, collection_id: str):
        """Invalida cache de búsquedas para una colección."""
        if not self.redis:
            return
        
        try:
            # Buscar todas las claves de cache para esta colección
            cache_pattern = f"search_cache:{collection_id}:*"
            cache_keys = await self.redis.keys(cache_pattern)
            
            # Eliminar claves encontradas
            if cache_keys:
                await self.redis.delete(*cache_keys)
                logger.info(f"Cache de búsqueda invalidado para collection {collection_id}: {len(cache_keys)} claves")
            
        except Exception as e:
            logger.error(f"Error invalidando search cache: {str(e)}")