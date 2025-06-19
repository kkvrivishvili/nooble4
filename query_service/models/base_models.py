"""
Base Pydantic models and constants for the Query Service interface.

These models are intended to be reused by specific action payload definitions.
"""
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

# --- Action Type Constants for Query Service --- #
ACTION_QUERY_GENERATE = "query.generate"  # For RAG-based generation
ACTION_QUERY_LLM_DIRECT = "query.llm.direct"  # For direct LLM interaction
ACTION_QUERY_SEARCH = "query.search"      # For vector search only
ACTION_QUERY_STATUS = "query.status"      # For checking the status of a query

# --- Common Reusable Models --- #

class QueryServiceLLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    # Add other providers as needed

class QueryServiceLLMConfig(BaseModel):
    """Configuration for the language model used by Query Service."""
    provider: QueryServiceLLMProvider = Field(default=QueryServiceLLMProvider.GROQ)
    model_name: str = Field(default="llama-3.3-70b-versatile")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    stream: bool = Field(default=False, description="Indicates if streaming is preferred. QueryService handles actual streaming.")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop_sequences: Optional[List[str]] = Field(None, description="Sequences to stop generation at.")
    user_id: Optional[str] = Field(None, description="Optional user ID for tracking/moderation by LLM provider.")

    model_config = {"extra": "forbid"}

class QueryServiceChatMessage(BaseModel):
    """Represents a single message in a chat conversation for Query Service."""
    role: str = Field(..., description="Role of the message sender (e.g., 'user', 'assistant', 'system', 'tool').")
    content: Optional[str] = Field(None, description="Text content of the message.")
    name: Optional[str] = Field(None, description="Optional name for 'tool' role messages or function name for 'assistant' role tool calls.")
    
    # For assistant messages that call tools (aligns with OpenAI tool_calls structure)
    # Each dict in tool_calls should have 'id', 'type' ('function'), and 'function' ({'name': ..., 'arguments': ...}).
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls requested by the assistant.")
    
    # For tool messages providing results
    tool_call_id: Optional[str] = Field(None, description="ID of the tool call this message is a result for.")

    model_config = {"extra": "allow"} # Allow extra for flexibility

class QueryServiceToolFunctionParameters(BaseModel):
    """Describes the parameters for a tool function (JSON Schema)."""
    type: str = Field(default="object")
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

    model_config = {"extra": "forbid"}

class QueryServiceToolFunction(BaseModel):
    """Describes the function within a tool for Query Service."""
    name: str = Field(..., description="The name of the function to be called.")
    description: Optional[str] = Field(None, description="A description of what the function does.")
    parameters: QueryServiceToolFunctionParameters = Field(..., description="JSON Schema object describing the parameters the function accepts.")

    model_config = {"extra": "forbid"}

class QueryServiceToolDefinition(BaseModel):
    """Defines a tool that can be called by the LLM (aligns with OpenAI)."""
    type: str = Field(default="function", description="The type of tool, currently only 'function' is supported.")
    function: QueryServiceToolFunction = Field(..., description="The function definition.")

    model_config = {"extra": "forbid"}

class RetrievedDoc(BaseModel):
    """Represents a document chunk retrieved during a search operation."""
    id: str = Field(..., description="Unique ID of the retrieved chunk/document.")
    text: str = Field(..., description="Content of the retrieved chunk/document.")
    score: float = Field(..., description="Similarity score of the retrieval.")
    collection_id: Optional[str] = Field(None, description="ID of the collection from which the document was retrieved.")
    document_id: Optional[str] = Field(None, description="Original ID of the document if applicable.")
    document_title: Optional[str] = Field(None, description="Title of the original document.")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata associated with the document.")

    model_config = {"extra": "forbid"}

class QueryErrorResponseData(BaseModel):
    """Standardized error response data for Query Service actions."""
    query_id: Optional[str] = Field(None, description="ID of the query if available.")
    action: Optional[str] = Field(None, description="The action that was attempted, e.g., 'query.generate'.")
    error_type: str = Field(..., description="Type of error, e.g., 'ValidationError', 'LLMError', 'SearchUnavailable'.")
    error_message: str = Field(..., description="A descriptive error message.")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional details or context about the error.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}

class TokenUsage(BaseModel):
    """Represents token usage statistics from an LLM call."""
    prompt_tokens: Optional[int] = Field(None)
    completion_tokens: Optional[int] = Field(None)
    total_tokens: Optional[int] = Field(None)

    model_config = {"extra": "forbid"}
