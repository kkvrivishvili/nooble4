"""
Pydantic models for the 'query.search' action (vector search only).
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from .base_models import RetrievedDoc

# --- Payloads for ACTION_QUERY_SEARCH (Search Only) --- #

class QuerySearchPayload(BaseModel):
    """Payload for a vector search only call."""
    query_text: str = Field(..., description="The user's query for vector search.")
    collection_ids: List[str] = Field(..., description="List of collection IDs to search within.")
    top_k: int = Field(default=5, gt=0, description="Number of documents to retrieve.")
    filters: Optional[Dict[str, Any]] = Field(
        None, 
        description="Metadata filters for the search (e.g., {'source': 'website'}). Structure depends on vector DB capabilities."
    )
    similarity_threshold: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="Similarity threshold for filtering retrieved documents."
    )

    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("At least one collection_id is required for query.search")
        return v

    model_config = {"extra": "forbid"}

class QuerySearchResponseData(BaseModel):
    """Data part of the response for a vector search only call."""
    query_id: str = Field(..., description="ID unique to this query.search request.")
    retrieved_documents: List[RetrievedDoc] = Field(
        default_factory=list,
        description="List of documents retrieved."
    )
    total_results_before_limit: Optional[int] = Field(
        None, 
        description="Total number of results found before applying top_k or other limits."
    )
    
    # Timing (example from original payloads.py, can be refined)
    search_time_ms: Optional[int] = Field(None, description="Time taken for search in milliseconds.")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the response, e.g., collections_searched.")

    model_config = {"extra": "forbid"}
