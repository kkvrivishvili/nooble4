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
        agent_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RAGChunk]:
        """
        Realiza búsqueda vectorial en la colección unificada "documents".
        
        Args:
            agent_id: ID del agente - OBLIGATORIO para filtrado
            collection_ids: IDs de colecciones para filtro virtual (no nombres físicos)
        
        Returns:
            Lista de RAGChunk directamente
        """
        # Validar agent_id obligatorio
        if not agent_id:
            raise ValueError("agent_id is required for vector search")
        
        # Construir filtro con tenant_id, agent_id Y collection_ids virtuales
        must_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id))
            ),
            # Filtro obligatorio por agent_id
            FieldCondition(
                key="agent_id",
                match=MatchValue(value=str(agent_id))
            )
        ]
        
        # CAMBIO CRÍTICO: collection_ids como filtro virtual, no colecciones físicas
        if collection_ids:
            must_conditions.append(
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(any=collection_ids)  # Filtro virtual por collection_id
                )
            )
        
        qdrant_filter = Filter(must=must_conditions)
        
        self.logger.info(f"Searching vectors for agent_id={agent_id}, tenant_id={tenant_id}, collection_ids={collection_ids}")
        
        # Agregar filtros adicionales si existen
        if filters and filters.get("document_ids"):
            qdrant_filter.must.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(any=filters["document_ids"])
                )
            )
        
        # CAMBIO CRÍTICO: Buscar solo en colección unificada "documents"
        results = await self.client.search(
            collection_name="documents",  # Colección única
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=similarity_threshold,
            with_payload=True
        )
        
        # Convertir a RAGChunk CON agent_id y collection_id del payload
        all_results = []
        for hit in results:
            chunk = RAGChunk(
                chunk_id=str(hit.id),
                content=hit.payload.get("content", ""),  # Ya usa 'content' 
                document_id=UUID(hit.payload.get("document_id", str(UUID(int=0)))),
                collection_id=hit.payload.get("collection_id", ""),  # Del payload, no parámetro
                similarity_score=hit.score,
                metadata={
                    **hit.payload.get("metadata", {}),
                    "agent_id": hit.payload.get("agent_id", agent_id),  # Incluir agent_id
                    "tenant_id": hit.payload.get("tenant_id", str(tenant_id))
                }
            )
            all_results.append(chunk)
        
        # Ordenar por score
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        self.logger.info(f"Found {len(all_results)} chunks for agent_id={agent_id}")
        
        # Retornar solo top_k globales
        return all_results[:top_k]
    
    async def close(self):
        """Cierra el cliente."""
        await self.client.close()