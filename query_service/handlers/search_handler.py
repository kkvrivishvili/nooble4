"""
Handler para búsqueda vectorial sin generación LLM.

Este handler maneja búsquedas puras en el vector store,
útil cuando solo se necesitan recuperar documentos relevantes
sin generar una respuesta.
"""

import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
import hashlib
import json

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models.payloads import QuerySearchResponse, SearchResult
from ..clients.vector_client import VectorClient
from ..utils.cache_manager import QueryCacheManager


class SearchHandler(BaseHandler):
    """
    Handler para búsqueda vectorial pura.
    
    Realiza búsquedas en el vector store y retorna los documentos
    más relevantes sin procesamiento adicional con LLM.
    """
    
    def __init__(self, app_settings, direct_redis_conn):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para caché
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Cliente de vector store
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.http_timeout_seconds
        )
        
        # Cache manager
        self.cache_manager = QueryCacheManager(
            redis_conn=direct_redis_conn,
            app_settings=app_settings
        )
        
        # Configuración por defecto
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        
        self._logger.info("SearchHandler inicializado")
    
    async def search_documents(
        self,
        query_text: str,
        collection_ids: List[str],
        tenant_id: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        trace_id: Optional[UUID] = None
    ) -> QuerySearchResponse:
        """
        Realiza una búsqueda vectorial en las colecciones especificadas.
        
        Args:
            query_text: Texto de búsqueda
            collection_ids: IDs de colecciones donde buscar
            tenant_id: ID del tenant
            top_k: Número de resultados
            similarity_threshold: Umbral de similitud
            filters: Filtros adicionales
            trace_id: ID de traza
            
        Returns:
            QuerySearchResponse con los resultados
        """
        start_time = time.time()
        query_id = str(trace_id) if trace_id else str(UUID())
        
        # Usar valores por defecto si no se especifican
        top_k = top_k or self.default_top_k
        similarity_threshold = similarity_threshold or self.similarity_threshold
        
        self._logger.info(
            f"Búsqueda vectorial: '{query_text[:50]}...' en colecciones {collection_ids}",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "top_k": top_k
            }
        )
        
        try:
            # Generar clave de caché
            cache_key = self._generate_cache_key(
                query_text, collection_ids, top_k, similarity_threshold, filters
            )
            
            # Intentar obtener del caché
            cached_results = await self.cache_manager.get_cached_search(cache_key)
            if cached_results:
                self._logger.debug(f"Resultados obtenidos del caché para query_id: {query_id}")
                
                # Construir respuesta desde caché
                search_time_ms = 0  # Instantáneo desde caché
                return QuerySearchResponse(
                    query_id=query_id,
                    query_text=query_text,
                    search_results=cached_results,
                    total_results=len(cached_results),
                    search_time_ms=search_time_ms,
                    collections_searched=collection_ids,
                    metadata={"from_cache": True}
                )
            
            # Obtener embedding de la consulta (simulado por ahora)
            query_embedding = await self._get_query_embedding(query_text)
            
            # Realizar búsqueda en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id,
                filters=filters
            )
            
            # Cachear resultados si está habilitado
            if search_results and self.app_settings.search_cache_ttl > 0:
                await self.cache_manager.cache_search_results(
                    cache_key,
                    search_results,
                    ttl=self.app_settings.search_cache_ttl
                )
            
            # Calcular tiempo de búsqueda
            search_time_ms = int((time.time() - start_time) * 1000)
            
            # Registrar métricas
            await self._record_search_metrics(
                tenant_id=tenant_id,
                collections=collection_ids,
                results_count=len(search_results),
                search_time_ms=search_time_ms
            )
            
            # Construir respuesta
            response = QuerySearchResponse(
                query_id=query_id,
                query_text=query_text,
                search_results=search_results,
                total_results=len(search_results),
                search_time_ms=search_time_ms,
                collections_searched=collection_ids,
                metadata={
                    "similarity_threshold": similarity_threshold,
                    "filters_applied": filters is not None
                }
            )
            
            self._logger.info(
                f"Búsqueda completada en {search_time_ms}ms con {len(search_results)} resultados",
                extra={
                    "query_id": query_id,
                    "results_count": len(search_results),
                    "search_time_ms": search_time_ms
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error en búsqueda vectorial: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error realizando búsqueda vectorial: {str(e)}",
                original_exception=e
            )
    
    async def _get_query_embedding(self, query_text: str) -> List[float]:
        """
        Obtiene el embedding de la consulta.
        
        TODO: Implementar llamada real al Embedding Service.
        """
        self._logger.debug("Generando embedding simulado para búsqueda")
        
        # Simulación: generar vector basado en hash del texto para consistencia
        import random
        
        # Usar hash del texto como semilla para reproducibilidad
        seed = int(hashlib.md5(query_text.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        embedding_dim = 1536
        embedding = [random.gauss(0, 1) for _ in range(embedding_dim)]
        
        # Normalizar
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    def _generate_cache_key(
        self,
        query_text: str,
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Genera una clave única para cachear resultados de búsqueda.
        """
        # Crear una representación única de los parámetros
        key_data = {
            "query": query_text.lower().strip(),
            "collections": sorted(collection_ids),
            "top_k": top_k,
            "threshold": similarity_threshold,
            "filters": filters or {}
        }
        
        # Generar hash
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        
        return f"search:{key_hash}"
    
    async def _record_search_metrics(
        self,
        tenant_id: str,
        collections: List[str],
        results_count: int,
        search_time_ms: int
    ):
        """
        Registra métricas de búsqueda para análisis.
        """
        try:
            # Clave para métricas diarias
            date_key = time.strftime("%Y%m%d")
            metrics_key = f"metrics:search:{tenant_id}:{date_key}"
            
            # Incrementar contadores
            pipeline = self.direct_redis_conn.pipeline()
            
            # Contador de búsquedas
            pipeline.hincrby(metrics_key, "total_searches", 1)
            
            # Contador por colección
            for collection in collections:
                pipeline.hincrby(metrics_key, f"collection:{collection}", 1)
            
            # Acumular tiempo total y resultados
            pipeline.hincrby(metrics_key, "total_time_ms", search_time_ms)
            pipeline.hincrby(metrics_key, "total_results", results_count)
            
            # TTL de 7 días para métricas
            pipeline.expire(metrics_key, 7 * 24 * 3600)
            
            await pipeline.execute()
            
        except Exception as e:
            # No fallar la búsqueda por error en métricas
            self._logger.warning(f"Error registrando métricas de búsqueda: {e}")
    
    async def validate_collections(
        self,
        collection_ids: List[str],
        tenant_id: str
    ) -> List[str]:
        """
        Valida que las colecciones existan y el tenant tenga acceso.
        
        Returns:
            Lista de collection_ids válidos
        """
        # TODO: Implementar validación real contra Agent Management Service
        # Por ahora, asumimos que todas las colecciones son válidas
        
        self._logger.debug(f"Validando acceso a colecciones {collection_ids} para tenant {tenant_id}")
        return collection_ids
