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

from ..clients.qdrant_client import QdrantClient
from ..clients.embedding_client import EmbeddingClient


class RAGHandler(BaseHandler):
    """Handler para búsqueda RAG pura (knowledge tool)."""
    
    def __init__(self, app_settings, embedding_client: EmbeddingClient, qdrant_client: QdrantClient, direct_redis_conn=None):
        """
        Inicializa el handler para procesamiento RAG avanzado recibiendo los clientes como dependencias.
        
        Args:
            app_settings: Configuración global de la aplicación
            embedding_client: Cliente para comunicación con Embedding Service
            qdrant_client: Cliente para búsqueda vectorial en Qdrant
            direct_redis_conn: Conexión Redis directa (opcional)
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Validar que todos los clientes requeridos estén presentes
        if not embedding_client:
            raise ValueError("embedding_client es requerido para RAGHandler")
        if not qdrant_client:
            raise ValueError("qdrant_client es requerido para RAGHandler")
            
        # Asignar los clientes recibidos como dependencias
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        
        self._logger.info("RAGHandler inicializado con inyección de clientes")
    
    async def process_rag_search(
        self,
        query_text: str,
        rag_config: RAGConfig,
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID,
        agent_id: UUID
    ) -> RAGSearchResult:
        """Procesa una búsqueda RAG (knowledge tool)."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        self._logger.info(
            f"Iniciando búsqueda RAG para query: {query_text[:100]}...",
            extra={
                "query_id": query_id,
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "agent_id": str(agent_id)
            }
        )
        
        try:
            # Usar configuración RAG centralizada
            embedding_request = EmbeddingRequest(
                input=query_text,
                model=rag_config.embedding_model,
                dimensions=rag_config.embedding_dimensions
            )
            
            # Obtener embedding de la consulta
            query_embedding = await self._get_query_embedding(
                embedding_request=embedding_request,
                rag_config=rag_config,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id,
                agent_id=agent_id
            )
            
            # 2. Buscar en vector store CON agent_id obligatorio
            try:
                search_results = await self.qdrant_client.search(
                    query_embedding=query_embedding,
                    collection_ids=rag_config.collection_ids,
                    top_k=rag_config.top_k,
                    similarity_threshold=rag_config.similarity_threshold,
                    tenant_id=tenant_id,
                    agent_id=str(agent_id),  # NUEVO: agent_id obligatorio para filtrado
                    filters={"document_ids": rag_config.document_ids} if rag_config.document_ids else None
                )
            except Exception as e:
                self._logger.error(
                    f"Error during vector search for query_id {query_id}: {e}",
                    extra={
                        "query_id": query_id,
                        "tenant_id": str(tenant_id),
                        "agent_id": str(agent_id)
                    },
                    exc_info=True
                )
                raise ExternalServiceError(f"Failed to perform vector search in Qdrant: {e}")
            
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
        rag_config: RAGConfig,
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        agent_id: UUID,
    ) -> List[float]:
        """Obtiene el embedding usando el Embedding Service con configuración RAG."""
        response = await self.embedding_client.get_embeddings(
            texts=[embedding_request.input],
            rag_config=rag_config,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            trace_id=trace_id
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
        
        # CORRECCIÓN 4: Manejar la estructura correcta de respuesta de embeddings
        embeddings_data = response.data.get("embeddings", [])
        if not embeddings_data:
            raise ExternalServiceError("No se recibieron embeddings del Embedding Service")
        
        # Manejar la estructura correcta: lista de objetos con chunk_id, embedding, error
        first_result = embeddings_data[0]
        if "error" in first_result and first_result["error"]:
            raise ExternalServiceError(f"Error en embedding: {first_result['error']}")
        
        # Extraer el embedding del primer resultado
        embedding = first_result.get("embedding", [])
        if not embedding:
            raise ExternalServiceError("No se recibió embedding válido del Embedding Service")
        
        return embedding