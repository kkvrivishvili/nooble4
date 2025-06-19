"""
Handler para búsqueda RAG (knowledge tool).
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models import (
    QueryRAGPayload,
    QueryRAGResponseData,
    RAGChunk
)
from ..clients.vector_client import VectorClient
from ..clients.embedding_client import EmbeddingClient


class RAGHandler(BaseHandler):
    """Handler para búsqueda RAG pura (knowledge tool)."""
    
    def __init__(self, app_settings, embedding_client: EmbeddingClient, direct_redis_conn=None):
        """
        Inicializa el handler.
        
        Args:
            app_settings: QueryServiceSettings
            embedding_client: Cliente para obtener embeddings
            direct_redis_conn: Conexión Redis directa
        """
        super().__init__(app_settings, direct_redis_conn)
        
        if not embedding_client:
            raise ValueError("embedding_client es requerido para RAGHandler")
            
        self.embedding_client = embedding_client
        
        # TODO: Cambiar a Qdrant local cuando esté implementado
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.search_timeout_seconds
        )
        
        self._logger.info("RAGHandler inicializado")
    
    async def process_rag_search(
        self,
        payload: QueryRAGPayload,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID
    ) -> QueryRAGResponseData:
        """Procesa una búsqueda RAG (knowledge tool)."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            self._logger.info(
                f"Procesando búsqueda RAG: '{payload.query_text[:50]}...'",
                extra={
                    "query_id": query_id,
                    "collections": payload.collection_ids,
                    "top_k": payload.top_k
                }
            )
            
            # 1. Obtener embedding de la consulta
            query_embedding = await self._get_query_embedding(
                query_text=payload.query_text,
                embedding_config=payload.embedding_config,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id
            )
            
            # 2. Buscar en vector store
            # TODO: Implementar búsqueda en Qdrant local
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=payload.collection_ids,
                top_k=payload.top_k,
                similarity_threshold=payload.similarity_threshold,
                tenant_id=tenant_id,
                filters={"document_ids": payload.document_ids} if payload.document_ids else None
            )
            
            # 3. Convertir resultados a RAGChunk
            chunks = []
            for result in search_results:
                chunk = RAGChunk(
                    content=result.content,
                    source=result.collection_id,
                    document_id=result.document_id if hasattr(result, 'document_id') else None,
                    score=result.similarity_score,
                    metadata=result.metadata if hasattr(result, 'metadata') else {}
                )
                chunks.append(chunk)
            
            search_time_ms = int((time.time() - start_time) * 1000)
            
            return QueryRAGResponseData(
                chunks=chunks,
                total_found=len(chunks),
                query_id=query_id,
                search_time_ms=search_time_ms
            )
            
        except Exception as e:
            self._logger.error(f"Error en RAG search: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando búsqueda RAG: {str(e)}")
    
    async def _get_query_embedding(
        self,
        query_text: str,
        embedding_config: dict,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID
    ) -> List[float]:
        """Obtiene el embedding usando el Embedding Service."""
        response = await self.embedding_client.request_query_embedding(
            query_text=query_text,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            model=embedding_config.model
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        return response.data.get("embedding", [])