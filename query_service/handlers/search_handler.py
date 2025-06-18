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


class SearchHandler(BaseHandler):
    """
    Handler para búsqueda vectorial pura.
    
    Realiza búsquedas en el vector store y retorna los documentos
    más relevantes sin procesamiento adicional con LLM.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Cliente de vector store
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.http_timeout_seconds
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
        trace_id: Optional[UUID] = None,
        embedding_client=None,
        session_id: Optional[str] = None,
        task_id: Optional[UUID] = None
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
            embedding_client: Cliente para obtener embeddings
            session_id: ID de sesión
            task_id: ID de la tarea
            
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
            # Obtener embedding de la consulta
            query_embedding = await self._get_query_embedding(
                query_text,
                tenant_id,
                session_id,
                trace_id,
                embedding_client,
                task_id
            )
            
            # Realizar búsqueda en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id,
                filters=filters
            )
            
            # Calcular tiempo de búsqueda
            search_time_ms = int((time.time() - start_time) * 1000)
            
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
    
    async def _get_query_embedding(
        self, 
        query_text: str,
        tenant_id: str,
        session_id: Optional[str],
        trace_id: Optional[UUID],
        embedding_client,
        task_id: Optional[UUID]
    ) -> List[float]:
        """
        Obtiene el embedding de la consulta.
        """
        # Si tenemos un cliente de embedding, usarlo
        if embedding_client and session_id and task_id:
            try:
                self._logger.debug("Solicitando embedding al Embedding Service")
                response = await embedding_client.request_query_embedding(
                    query_text=query_text,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id
                )
                # Asumiendo que la respuesta tiene un campo 'embedding' en data
                return response.data.get("embedding", [])
            except Exception as e:
                self._logger.warning(f"Error obteniendo embedding del servicio: {e}")
                # Continuar con embedding simulado
        
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