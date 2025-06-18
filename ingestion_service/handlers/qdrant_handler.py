from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from qdrant_client import QdrantClient
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
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "documents"
    ):
        super().__init__(app_settings)
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.client = QdrantClient(url=qdrant_url)
        self.vector_size = 1536  # Default for OpenAI embeddings
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure the collection exists with proper configuration"""
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                # Create payload indices for efficient filtering
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="tenant_id",
                    field_type="keyword"
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="collection_id", 
                    field_type="keyword"
                )
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="document_id",
                    field_type="keyword"
                )
                
                self._logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            self._logger.error(f"Error ensuring collection: {e}")
            raise
    
    async def store_chunks(self, chunks: List[ChunkModel]) -> Dict[str, Any]:
        """Store chunks with embeddings in Qdrant"""
        if not chunks:
            return {"stored": 0, "failed": 0}
        
        points = []
        failed_chunks = []
        
        for chunk in chunks:
            if not chunk.embedding:
                self._logger.warning(f"Chunk {chunk.chunk_id} has no embedding, skipping")
                failed_chunks.append(chunk.chunk_id)
                continue
            
            # Prepare payload
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "tenant_id": chunk.tenant_id,
                "collection_id": chunk.collection_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "keywords": chunk.keywords,
                "tags": chunk.tags,
                "metadata": chunk.metadata,
                "created_at": chunk.created_at.isoformat()
            }
            
            # Create point
            point = PointStruct(
                id=chunk.chunk_id,
                vector=chunk.embedding,
                payload=payload
            )
            points.append(point)
        
        # Batch upsert
        if points:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                self._logger.info(f"Stored {len(points)} chunks in Qdrant")
            except Exception as e:
                self._logger.error(f"Error storing chunks: {e}")
                raise
        
        return {
            "stored": len(points),
            "failed": len(failed_chunks),
            "failed_ids": failed_chunks
        }
    
    async def delete_document(
        self, 
        tenant_id: str, 
        document_id: str
    ) -> int:
        """Delete all chunks for a document"""
        try:
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=tenant_id)
                        ),
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            
            deleted_count = result.status
            self._logger.info(f"Deleted {deleted_count} chunks for document {document_id}")
            return deleted_count
            
        except Exception as e:
            self._logger.error(f"Error deleting document: {e}")
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


# ingestion_service/services/__init__.py
"""Services for Ingestion Service"""
from .ingestion_service import IngestionService

__all__ = ["IngestionService"]