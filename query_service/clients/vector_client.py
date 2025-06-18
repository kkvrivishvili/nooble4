"""
Cliente para el Vector Store.

Este cliente abstrae la comunicación con el servicio de
almacenamiento y búsqueda de vectores.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional

from common.errors.exceptions import ExternalServiceError
from ..models.payloads import SearchResult

class VectorClient:
    """Cliente para interactuar con un Vector Store."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Inicializa el cliente.
        
        Args:
            base_url: URL base del servicio de vectores.
            timeout: Timeout para las peticiones.
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._logger = logging.getLogger(__name__)
        
    async def search(
        self,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        tenant_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Realiza una búsqueda vectorial.
        
        Args:
            query_embedding: El vector de la consulta.
            collection_ids: IDs de las colecciones donde buscar.
            top_k: Número de resultados a devolver.
            similarity_threshold: Umbral de similitud.
            tenant_id: ID del tenant para filtrar.
            filters: Filtros adicionales.
            
        Returns:
            Una lista de SearchResult.
            
        Raises:
            ExternalServiceError: Si el servicio de vectores falla.
        """
        url = f"{self.base_url}/v1/search"
        
        payload = {
            "query_embedding": query_embedding,
            "collection_ids": collection_ids,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "tenant_id": tenant_id,
            "filters": filters or {}
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                self._logger.debug(f"Buscando en {len(collection_ids)} colecciones con top_k={top_k}")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                results_data = response.json().get("results", [])
                
                # Convertir resultados a modelos Pydantic
                search_results = [SearchResult(**item) for item in results_data]
                
                self._logger.info(f"Búsqueda vectorial retornó {len(search_results)} resultados")
                
                return search_results
                
            except httpx.HTTPStatusError as e:
                self._logger.error(f"Error de estado HTTP del Vector Store: {e.response.status_code} - {e.response.text}")
                raise ExternalServiceError(
                    f"Error en el Vector Store: {e.response.status_code}",
                    original_exception=e
                )
            except Exception as e:
                self._logger.error(f"Error inesperado con Vector Store: {e}")
                raise ExternalServiceError("Error inesperado al contactar Vector Store", original_exception=e)
