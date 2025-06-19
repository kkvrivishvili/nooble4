"""
Base Pydantic models and constants for the Query Service interface.

These models are intended to be reused by specific action payload definitions.
"""
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from uuid import UUID

# --- Action Type Constants for Query Service --- #
ACTION_QUERY_SIMPLE = "query.simple"      # For simple chat with automatic RAG
ACTION_QUERY_ADVANCE = "query.advance"    # For advanced chat with tools support
ACTION_QUERY_RAG = "query.rag"           # For knowledge tool search

# --- Common Reusable Models --- #

class QueryServiceLLMConfig(BaseModel):
    """Configuration for the language model used by Query Service."""
    provider: str = Field(..., description="LLM provider (e.g., 'groq')")
    model_name: str = Field(..., description="Model name")
    temperature: float = Field(..., ge=0.0, le=2.0)
    max_tokens: int = Field(..., gt=0)
    top_p: float = Field(..., ge=0.0, le=1.0)
    frequency_penalty: float = Field(..., ge=-2.0, le=2.0)
    presence_penalty: float = Field(..., ge=-2.0, le=2.0)
    stop_sequences: Optional[List[str]] = Field(None, description="Sequences to stop generation at.")

    model_config = {"extra": "forbid"}

class QueryServiceEmbeddingConfig(BaseModel):
    """Configuration for embeddings."""
    provider: str = Field(..., description="Embedding provider (e.g., 'openai')")
    model: str = Field(..., description="Embedding model name")
    dimensions: Optional[int] = Field(None, description="Vector dimensions")

    model_config = {"extra": "forbid"}

class QueryServiceChatMessage(BaseModel):
    """Represents a single message in a chat conversation."""
    role: str = Field(..., description="Role of the message sender (e.g., 'user', 'assistant', 'system', 'tool').")
    content: Optional[str] = Field(None, description="Text content of the message.")
    name: Optional[str] = Field(None, description="Optional name for 'tool' role messages.")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls requested by the assistant.")
    tool_call_id: Optional[str] = Field(None, description="ID of the tool call this message is a result for.")

    model_config = {"extra": "allow"}

class QueryServiceToolCall(BaseModel):
    """Represents a tool call made by the LLM."""
    id: str
    type: str = Field(default="function")
    function: Dict[str, Any]  # {name: str, arguments: str}

    model_config = {"extra": "forbid"}

class QueryServiceToolDefinition(BaseModel):
    """Defines a tool that can be called by the LLM."""
    type: str = Field(default="function", description="The type of tool, currently only 'function' is supported.")
    function: Dict[str, Any] = Field(..., description="The function definition.")

    model_config = {"extra": "forbid"}

class TokenUsage(BaseModel):
    """Represents token usage statistics from an LLM call."""
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)

    model_config = {"extra": "forbid"}

class RAGChunk(BaseModel):
    """Represents a chunk retrieved from RAG search."""
    content: str = Field(..., description="Content of the chunk")
    source: str = Field(..., description="Collection ID where the chunk was found")
    document_id: Optional[str] = Field(None, description="Document ID if filtering was applied")
    score: float = Field(..., description="Similarity score")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}