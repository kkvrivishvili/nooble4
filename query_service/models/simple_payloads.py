"""
Pydantic models for the 'query.simple' action (simple chat with automatic RAG).
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

from .base_models import (
    QueryServiceLLMConfig,
    QueryServiceEmbeddingConfig,
    QueryServiceChatMessage,
    TokenUsage
)

class QuerySimplePayload(BaseModel):
    """Payload for query.simple - simple chat with automatic RAG."""
    user_message: str = Field(..., description="The user's message")
    collection_ids: List[str] = Field(..., description="List of collection IDs to search within")
    document_ids: Optional[List[str]] = Field(None, description="Optional list of document IDs to filter")
    conversation_history: Optional[List[QueryServiceChatMessage]] = Field(
        default_factory=list,
        description="Optional conversation history"
    )
    agent_config: QueryServiceLLMConfig = Field(..., description="LLM configuration")
    embedding_config: QueryServiceEmbeddingConfig = Field(..., description="Embedding configuration")
    system_prompt: str = Field(..., description="System prompt for the conversation")
    
    # RAG parameters
    top_k: int = Field(..., gt=0, description="Number of chunks to retrieve")
    similarity_threshold: float = Field(..., ge=0.0, le=1.0, description="Similarity threshold")

    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("At least one collection_id is required")
        return v

    model_config = {"extra": "forbid"}

class QuerySimpleResponseData(BaseModel):
    """Response data for query.simple."""
    message: str = Field(..., description="The AI's response")
    sources: List[str] = Field(default_factory=list, description="List of source document IDs used")
    usage: TokenUsage = Field(..., description="Token usage statistics")
    query_id: str = Field(..., description="Unique query ID")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}