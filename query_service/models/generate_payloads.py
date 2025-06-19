"""
Pydantic models for the 'query.generate' action (RAG-based generation).
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from .base_models import (
    QueryServiceLLMConfig,
    QueryServiceChatMessage,
    RetrievedDoc,
    TokenUsage
)

# --- Payload for ACTION_QUERY_GENERATE (RAG) --- #

class QueryGeneratePayload(BaseModel):
    """Payload for a RAG-based generation call."""
    query_text: str = Field(..., description="The user's query for RAG.")
    collection_ids: List[str] = Field(..., description="List of collection IDs to search within.")
    
    conversation_history: Optional[List[QueryServiceChatMessage]] = Field(
        default_factory=list,
        description="Optional conversation history to provide context."
    )
    llm_config: QueryServiceLLMConfig = Field(
        default_factory=QueryServiceLLMConfig,
        description="Configuration for the LLM."
    )
    system_prompt_template: Optional[str] = Field(
        None,
        description="Optional template for the system prompt. If None, QueryService uses a default. Variables: {context_str}, {query_str}."
    )
    
    # RAG specific parameters
    top_k_retrieval: int = Field(default=5, description="Number of documents to retrieve.")
    similarity_threshold: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="Similarity threshold for filtering retrieved documents."
    )
    response_mode: Optional[str] = Field(
        "default", 
        description="Modo de respuesta (e.g., 'default', 'fast', 'creative') - from original payloads.py, consider if needed"
    )

    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("At least one collection_id is required for query.generate")
        return v

    model_config = {"extra": "forbid"}

class QueryGenerateResponseData(BaseModel):
    """Data part of the response for a RAG-based generation call."""
    query_id: str = Field(..., description="ID unique to this query.generate request.")
    ai_response: str = Field(..., description="The AI's response message, generated with RAG context.")
    retrieved_documents: List[RetrievedDoc] = Field(
        default_factory=list,
        description="List of documents retrieved and used for generation."
    )
    llm_model_info: Optional[Dict[str, Any]] = Field(
        None, 
        description="Information about the LLM used (e.g., name, provider). Derived from llm_config or actual model used."
    )
    usage: Optional[TokenUsage] = Field(None, description="Token usage statistics.")
    
    # Timing (example from original payloads.py, can be refined)
    search_time_ms: Optional[int] = Field(None, description="Time taken for search in milliseconds.")
    generation_time_ms: Optional[int] = Field(None, description="Time taken for LLM generation in milliseconds.")
    total_time_ms: Optional[int] = Field(None, description="Total processing time in milliseconds.")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the response.")

    model_config = {"extra": "forbid"}
