from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    Filter, FieldCondition, MatchValue, PointIdsList
)
import numpy as np

from common.handlers import BaseHandler
from common.config import CommonAppSettings
from ..models import ChunkModel


class QdrantHandler(BaseHandler):
    """Handler for Qdrant vector database operations"""
    
    def __init__(
        self, 
        app_settings: CommonAppSettings,
        qdrant_client: AsyncQdrantClient,  
        collection_name: str = "documents"
    ):
        super().__init__(app_settings)
        self.collection_name = collection_name
        self.client = qdrant_client  
        self.vector_size = 1536  # Default for OpenAI embeddings
        self._initialized = False
        
    async def initialize(self):
        """Initialize the handler and ensure collection exists"""
        if not self._initialized:
            await self._ensure_collection()
            self._initialized = True
    
    async def _ensure_collection(self):
        """Ensure the collection exists with proper configuration"""
        try:
            collections_response = await self.client.get_collections()
            collections = collections_response.collections
            if not any(c.name == self.collection_name for c in collections):
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                # Create payload indices for efficient filtering
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_type="keyword"
                )
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="agent_id",
                    field_type="keyword"
                )
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="collection_id", 
                    field_type="keyword"
                )
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_type="keyword"
                )
                
                self._logger.info(f"Collection '{self.collection_name}' created with indices")
            else:
                self._logger.info(f"Collection '{self.collection_name}' already exists")
                
        except Exception as e:
            self._logger.error(f"Error ensuring collection '{self.collection_name}': {e}")
            raise
    
    async def store_chunks(self, chunks: List[ChunkModel]) -> Dict[str, Any]:
        """Store chunks with embeddings in Qdrant."""
        if not chunks:
            return {"stored": 0, "failed": 0, "failed_ids": []}

        points = []
        failed_chunks = []

        for chunk in chunks:
            if not chunk.embedding:
                self._logger.warning(f"Chunk {chunk.chunk_id} has no embedding, skipping")
                failed_chunks.append(chunk.chunk_id)
                continue

            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "tenant_id": chunk.tenant_id,
                "collection_id": chunk.collection_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "keywords": chunk.keywords,
                "tags": chunk.tags,
                "created_at": chunk.created_at.isoformat(),
            }
            # Se fusiona la metadata custom, que debe contener el agent_id
            if chunk.metadata:
                payload.update(chunk.metadata)

            point = PointStruct(
                id=chunk.chunk_id,
                vector=chunk.embedding,
                payload=payload
            )
            points.append(point)

        if points:
            try:
                await self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True
                )
                self._logger.info(f"Stored {len(points)} chunks in Qdrant for agent_id: {agent_id}")
            except Exception as e:
                self._logger.error(f"Error storing chunks: {e}")
                # If the batch fails, we consider all points in it as failed
                failed_chunks.extend([p.id for p in points])

        return {
            "stored": len(points) - len(failed_chunks),
            "failed": len(failed_chunks),
            "failed_ids": failed_chunks,
        }
    
    async def delete_document(
        self, 
        tenant_id: str, 
        document_id: str, 
        collection_id: str, 
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete all chunks for a document, filtered by collection_id and optionally agent_id."""
        try:
            filters = [
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id)
                ),
                FieldCondition(
                    key="collection_id",
                    match=MatchValue(value=collection_id)
                ),
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]

            if agent_id:
                filters.append(
                    FieldCondition(
                        key="agent_id",
                        match=MatchValue(value=agent_id)
                    )
                )

            result = await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(must=must_conditions)
            )

            # The result object in v1.1.0+ of qdrant_client might not have a direct status count.
            # We check the result status. Assuming result is an UpdateResult.
            if result and result.status == "completed":
                # Qdrant's delete doesn't return the count of deleted points directly.
                # We log the operation's success.
                log_message = f"Delete operation completed for document {document_id}"
                if agent_id:
                    log_message += f" for agent {agent_id}"
                self._logger.info(log_message)
                # Returning 1 to indicate success, as count is not available.
                # A more robust implementation might need a count operation before deleting.
                return 1 
            else:
                self._logger.warning(f"Delete operation for document {document_id} may not have completed successfully.")
                return 0

        except Exception as e:
            self._logger.error(f"Error deleting document {document_id}: {e}")
            raise
    
    async def get_collection_stats(
        self, 
        tenant_id: str, 
        collection_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics for a tenant/collection"""
        try:
            # Build filter
            must_conditions = [
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
            
            if collection_id:
                must_conditions.append(
                    FieldCondition(
                        key="collection_id",
                        match=MatchValue(value=collection_id)
                    )
                )
            
            # Count points
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=Filter(must=must_conditions)
            )
            
            return {
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "total_chunks": count_result.count,
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            self._logger.error(f"Error getting stats: {e}")
            raise