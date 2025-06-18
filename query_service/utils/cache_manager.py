"""
Gestor de caché para Query Service.

Este módulo proporciona una clase para manejar la lógica de caché
para resultados de búsqueda y respuestas RAG.
"""

import logging
import json
import hashlib
from typing import List, Optional, Dict, Any

from ..models.payloads import SearchResult, QueryGenerateResponse

class QueryCacheManager:
    """Gestiona el caché de consultas en Redis."""
    
    def __init__(self, redis_conn, app_settings):
        """
        Inicializa el gestor de caché.
        
        Args:
            redis_conn: Conexión directa a Redis.
            app_settings: Configuración del servicio.
        """
        self.redis_conn = redis_conn
        self.app_settings = app_settings
        self._logger = logging.getLogger(__name__)
        
    def get_search_cache_key(
        self,
        query_text: str,
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Genera una clave de caché única para una búsqueda.
        """
        key_data = {
            "query": query_text.lower().strip(),
            "collections": sorted(collection_ids),
            "top_k": top_k,
            "threshold": similarity_threshold,
            "filters": filters or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]
        return f"search:{key_hash}"
        
    async def get_cached_search(self, cache_key: str) -> Optional[List[SearchResult]]:
        """
        Obtiene resultados de búsqueda desde el caché.
        """
        if not self.app_settings.search_cache_ttl > 0:
            return None
            
        try:
            cached_data = await self.redis_conn.get(cache_key)
            if cached_data:
                self._logger.debug(f"Cache hit para búsqueda con clave: {cache_key}")
                results_json = json.loads(cached_data)
                return [SearchResult(**item) for item in results_json]
        except Exception as e:
            self._logger.warning(f"Error al leer caché de búsqueda: {e}")
        return None

    async def cache_search_results(self, cache_key: str, results: List[SearchResult], ttl: int):
        """
        Cachea los resultados de una búsqueda vectorial.
        """
        if not ttl > 0:
            return
            
        try:
            results_json = json.dumps([r.model_dump() for r in results])
            await self.redis_conn.set(cache_key, results_json, ex=ttl)
            self._logger.debug(f"Resultados de búsqueda cacheados con clave: {cache_key}")
        except Exception as e:
            self._logger.warning(f"Error al escribir en caché de búsqueda: {e}")

    async def get_cached_rag_result(self, query_id: str) -> Optional[QueryGenerateResponse]:
        """
        Obtiene una respuesta RAG completa desde el caché.
        """
        if not self.app_settings.rag_cache_ttl > 0:
            return None

        cache_key = f"rag:{query_id}"
        try:
            cached_data = await self.redis_conn.get(cache_key)
            if cached_data:
                self._logger.debug(f"Cache hit para RAG con clave: {cache_key}")
                response_json = json.loads(cached_data)
                return QueryGenerateResponse(**response_json)
        except Exception as e:
            self._logger.warning(f"Error al leer caché RAG: {e}")
        return None

    async def cache_rag_result(self, query_id: str, response: QueryGenerateResponse, ttl: int):
        """
        Cachea una respuesta RAG completa.
        """
        if not ttl > 0:
            return

        cache_key = f"rag:{query_id}"
        try:
            response_json = response.model_dump_json()
            await self.redis_conn.set(cache_key, response_json, ex=ttl)
            self._logger.debug(f"Respuesta RAG cacheada con clave: {cache_key}")
        except Exception as e:
            self._logger.warning(f"Error al escribir en caché RAG: {e}")
