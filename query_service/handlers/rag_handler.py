"""
Handler para búsqueda RAG (knowledge tool).
"""
import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError
from common.models.chat_models import (
    RAGConfig,
    RAGChunk,
    RAGSearchResult,
    EmbeddingRequest
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
        
        # Inicializar vector client
        self.vector_client = VectorClient(
            base_url=str(app_settings.qdrant_url) if hasattr(app_settings, 'qdrant_url') and app_settings.qdrant_url else "http://localhost:6333",
            timeout=app_settings.search_timeout_seconds
        )
        
        self._logger.info("RAGHandler inicializado")
    
    async def process_rag_search(
        self,
        query_text: str,
        rag_config: RAGConfig,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> RAGSearchResult:
        """Procesa una búsqueda RAG (knowledge tool)."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            self._logger.info(
                f"Procesando búsqueda RAG: '{query_text[:50]}...'",
                extra={
                    "query_id": query_id,
                    "collections": rag_config.collection_ids,
                    "top_k": top_k or rag_config.top_k
                }
            )
            
            # Usar valores override si se proporcionan
            actual_top_k = top_k if top_k is not None else rag_config.top_k
            actual_threshold = similarity_threshold if similarity_threshold is not None else rag_config.similarity_threshold
            
            # 1. Obtener embedding de la consulta
            embedding_request = EmbeddingRequest(
                input=query_text,
                model=rag_config.embedding_model,
                dimensions=rag_config.embedding_dimensions
            )
            
            query_embedding = await self._get_query_embedding(
                embedding_request=embedding_request,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id
            )
            
            # 2. Buscar en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=rag_config.collection_ids,
                top_k=actual_top_k,
                similarity_threshold=actual_threshold,
                tenant_id=tenant_id,
                filters={"document_ids": rag_config.document_ids} if rag_config.document_ids else None
            )
            
            # 3. Convertir resultados a RAGChunk
            chunks = []
            for result in search_results:
                chunk = RAGChunk(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    document_id=result.document_id if hasattr(result, 'document_id') else "",
                    collection_id=result.collection_id,
                    similarity_score=result.similarity_score,
                    metadata=result.metadata if hasattr(result, 'metadata') else {}
                )
                chunks.append(chunk)
            
            search_time_ms = int((time.time() - start_time) * 1000)
            
            return RAGSearchResult(
                chunks=chunks,
                total_found=len(chunks),
                search_time_ms=search_time_ms
            )
            
        except Exception as e:
            self._logger.error(f"Error en RAG search: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando búsqueda RAG: {str(e)}")
    
    async def _get_query_embedding(
        self,
        embedding_request: EmbeddingRequest,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID
    ) -> List[float]:
        """Obtiene el embedding usando el Embedding Service."""
        response = await self.embedding_client.request_query_embedding(
            query_text=embedding_request.input,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            model=embedding_request.model.value  # Usar el valor del enum
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        return response.data.get("embedding", [])