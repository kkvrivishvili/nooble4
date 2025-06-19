"""
Pydantic models for the 'query.rag' action (knowledge tool search).
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

from .base_models import (
    QueryServiceEmbeddingConfig,
    RAGChunk
)

class QueryRAGPayload(BaseModel):
    """Payload for query.rag - knowledge tool search."""
    query_text: str = Field(..., description="Search query text")
    collection_ids: List[str] = Field(..., description="List of collection IDs to search")
    document_ids: Optional[List[str]] = Field(None, description="Optional document IDs to filter")
    embedding_config: QueryServiceEmbeddingConfig = Field(..., description="Embedding configuration")
    top_k: int = Field(..., gt=0, description="Number of chunks to retrieve")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity threshold")

    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("At least one collection_id is required")
        return v

    model_config = {"extra": "forbid"}

class QueryRAGResponseData(BaseModel):
    """Response data for query.rag."""
    chunks: List[RAGChunk] = Field(default_factory=list, description="Retrieved chunks")
    total_found: int = Field(..., description="Total number of chunks found")
    query_id: str = Field(..., description="Unique query ID")
    search_time_ms: int = Field(..., description="Search execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}