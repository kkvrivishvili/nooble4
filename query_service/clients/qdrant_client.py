"""
Cliente para Qdrant usando el SDK oficial.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Filter, FieldCondition, MatchValue,
    SearchParams, PointStruct
)

from common.models.chat_models import RAGChunk


class QdrantClient:
    """Cliente oficial de Qdrant para búsquedas vectoriales."""
    
    def __init__(self, url: str, api_key: Optional[str] = None):
        """
        Inicializa el cliente de Qdrant.
        
        Args:
            url: URL de Qdrant
            api_key: API key opcional
        """
        self.client = AsyncQdrantClient(
            url=url,
            api_key=api_key,
            timeout=30
        )
        self.logger = logging.getLogger(__name__)
    
    async def search(
        self,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        tenant_id: UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RAGChunk]:
        """
        Realiza búsqueda vectorial en las colecciones.
        
        Returns:
            Lista de RAGChunk directamente
        """
        all_results = []
        
        # Construir filtro de tenant
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=str(tenant_id))
                )
            ]
        )
        
        # Agregar filtros adicionales si existen
        if filters and filters.get("document_ids"):
            qdrant_filter.must.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(any=filters["document_ids"])
                )
            )
        
        # Buscar en cada colección
        for collection_id in collection_ids:
            try:
                results = await self.client.search(
                    collection_name=collection_id,
                    query_vector=query_embedding,
                    query_filter=qdrant_filter,
                    limit=top_k,
                    score_threshold=similarity_threshold,
                    with_payload=True
                )
                
                # Convertir a RAGChunk
                for hit in results:
                    chunk = RAGChunk(
                        chunk_id=str(hit.id),
                        content=hit.payload.get("content", ""),
                        document_id=UUID(hit.payload.get("document_id", str(UUID(int=0)))),
                        collection_id=collection_id,
                        similarity_score=hit.score,
                        metadata=hit.payload.get("metadata", {})
                    )
                    all_results.append(chunk)
                    
            except Exception as e:
                self.logger.error(f"Error buscando en {collection_id}: {e}")
                continue
        
        # Ordenar por score
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Retornar solo top_k globales
        return all_results[:top_k]
    
    async def close(self):
        """Cierra el cliente."""
        await self.client.close()