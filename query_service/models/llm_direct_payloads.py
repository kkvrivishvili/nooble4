"""
Pydantic models for the 'query.llm.direct' action (direct LLM interaction).
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from .base_models import (
    QueryServiceLLMConfig,
    QueryServiceChatMessage,
    QueryServiceToolDefinition,
    TokenUsage
)

# --- Payloads for ACTION_QUERY_LLM_DIRECT --- #

class QueryLLMDirectPayload(BaseModel):
    """Payload for a direct LLM call (e.g., simple chat without RAG, ReAct agent LLM step)."""
    messages: List[QueryServiceChatMessage] = Field(
        ..., 
        description="Conversation history including the latest user message or system prompts."
    )
    llm_config: QueryServiceLLMConfig = Field(
        default_factory=QueryServiceLLMConfig,
        description="Configuration for the LLM."
    )
    tools: Optional[List[QueryServiceToolDefinition]] = Field(
        None, 
        description="List of tools available for the LLM to call."
    )
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(
        None, 
        description="Controls how the model selects tools. Can be 'none', 'auto', or a specific tool like {'type': 'function', 'function': {'name': 'my_function'}}."
    )
    # From original payloads.py, user_id is already in QueryServiceLLMConfig
    # user_id: Optional[str] = Field(None, description="ID de usuario") 

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        if not v:
            raise ValueError("At least one message is required for query.llm.direct")
        # Further validation for message roles and content can be done by QueryServiceChatMessage itself
        return v

    model_config = {"extra": "forbid"}


class QueryLLMDirectResponseData(BaseModel):
    """Data part of the response for a direct LLM call."""
    query_id: str = Field(..., description="ID unique to this query.llm.direct request.")
    message: QueryServiceChatMessage = Field(
        ..., 
        description="The AI's response message (can include content and/or tool_calls)."
    )
    finish_reason: Optional[str] = Field(None, description="Reason the LLM finished generating tokens (e.g., 'stop', 'length', 'tool_calls').")
    usage: Optional[TokenUsage] = Field(None, description="Token usage statistics.")
    
    # Timing (example from original payloads.py, can be refined)
    generation_time_ms: Optional[int] = Field(None, description="Time taken for LLM generation in milliseconds.")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the response.")

    model_config = {"extra": "forbid"}
