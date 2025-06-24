"""
Cliente para interactuar con el Vector Store (base de datos vectorial).

Proporciona una interfaz unificada para realizar búsquedas vectoriales,
independientemente del proveedor específico (Qdrant, Pinecone, etc.).
"""

import logging
import time
from typing import List, Optional, Dict, Any

from common.clients.base_http_client import BaseHTTPClient
from common.errors.http_errors import NotFoundError, ServiceUnavailableError

from ..models.payloads import SearchResult


class VectorClient(BaseHTTPClient):
    """
    Cliente para realizar búsquedas en el vector store.
    
    Implementa la comunicación con la API del vector store
    para búsquedas de similitud y recuperación de documentos.
    """
    
    def __init__(self, base_url: str, timeout: int):
        """
        Inicializa el cliente del vector store.
        
        Args:
            base_url: URL base del vector store
            timeout: Timeout para las peticiones (desde QueryServiceSettings)
        """
        super().__init__(base_url=base_url)
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    async def search(
        self,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        tenant_id: str = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Realiza una búsqueda vectorial en las colecciones especificadas.
        
        Args:
            query_embedding: Vector de embedding de la consulta
            collection_ids: IDs de las colecciones donde buscar
            top_k: Número máximo de resultados por colección (desde RAGConfig)
            similarity_threshold: Umbral mínimo de similitud (desde RAGConfig)
            tenant_id: ID del tenant para filtrado
            filters: Filtros adicionales específicos del vector store
            
        Returns:
            Lista de SearchResult ordenados por similitud
            
        Raises:
            NotFoundError: Si alguna colección no existe
            ServiceUnavailableError: Si el vector store no está disponible
        """
        start_time = time.time()
        
        # Preparar payload para la búsqueda
        payload = {
            "vector": query_embedding,
            "collections": collection_ids,
            "limit": top_k,
            "score_threshold": similarity_threshold
        }
        
        # Agregar filtros opcionales
        if tenant_id:
            if "filter" not in payload:
                payload["filter"] = {}
            payload["filter"]["tenant_id"] = tenant_id
        
        if filters:
            if "filter" not in payload:
                payload["filter"] = {}
            payload["filter"].update(filters)
        
        self.logger.debug(
            f"Búsqueda vectorial en colecciones {collection_ids}, "
            f"top_k={top_k}, threshold={similarity_threshold}"
        )
        
        try:
            # Realizar búsqueda
            response = await self.post(
                "/api/v1/search",
                json=payload,
                timeout=self.timeout
            )
            
            # Parsear respuesta
            data = response.json()
            
            # Convertir a SearchResult
            results = self._parse_search_results(data)
            
            # Log métricas
            elapsed = time.time() - start_time
            self.logger.info(
                f"Búsqueda completada en {elapsed:.2f}s. "
                f"Encontrados {len(results)} resultados"
            )
            
            return results
            
        except NotFoundError as e:
            # Una o más colecciones no existen
            self.logger.error(f"Colección no encontrada: {e}")
            raise
            
        except Exception as e:
            self.logger.error(f"Error en búsqueda vectorial: {e}")
            raise ServiceUnavailableError(
                f"Error al buscar en vector store: {str(e)}"
            )
    
    def _parse_search_results(self, response_data: Dict[str, Any]) -> List[SearchResult]:
        """
        Parsea la respuesta del vector store a objetos SearchResult.
        
        Args:
            response_data: Respuesta JSON del vector store
            
        Returns:
            Lista de SearchResult
        """
        results = []
        
        # La estructura exacta depende del vector store específico
        # Este es un ejemplo genérico que debería adaptarse
        
        search_results = response_data.get("results", [])
        
        for item in search_results:
            # Extraer campos según el formato del vector store
            result = SearchResult(
                chunk_id=item.get("id", ""),
                content=item.get("content", item.get("text", "")),
                similarity_score=item.get("score", 0.0),
                document_id=item.get("document_id", ""),
                document_title=item.get("document_title"),
                collection_id=item.get("collection_id", ""),
                metadata=item.get("metadata", {})
            )
            results.append(result)
        
        # Ordenar por score descendente
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return results
    
    async def get_collections(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista las colecciones disponibles.
        
        Args:
            tenant_id: Filtrar por tenant (opcional)
            
        Returns:
            Lista de colecciones con sus metadatos
        """
        try:
            params = {}
            if tenant_id:
                params["tenant_id"] = tenant_id
            
            response = await self.get(
                "/api/v1/collections",
                params=params
            )
            
            data = response.json()
            return data.get("collections", [])
            
        except Exception as e:
            self.logger.error(f"Error listando colecciones: {e}")
            raise ServiceUnavailableError(
                f"Error al listar colecciones: {str(e)}"
            )
    
    async def get_collection_info(self, collection_id: str) -> Dict[str, Any]:
        """
        Obtiene información detallada de una colección.
        
        Args:
            collection_id: ID de la colección
            
        Returns:
            Información de la colección
            
        Raises:
            NotFoundError: Si la colección no existe
        """
        try:
            response = await self.get(f"/api/v1/collections/{collection_id}")
            return response.json()
            
        except NotFoundError:
            self.logger.error(f"Colección {collection_id} no encontrada")
            raise
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info de colección: {e}")
            raise ServiceUnavailableError(
                f"Error al obtener información de colección: {str(e)}"
            )
    
    async def health_check(self) -> bool:
        """
        Verifica si el vector store está disponible.
        
        Returns:
            True si está disponible, False en caso contrario
        """
        try:
            response = await self.get("/health", timeout=5)
            return response.status_code == 200
            
        except Exception:
            return False
    
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()