"""
Pydantic models for the 'query.advance' action (advanced chat with tools).
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

from .base_models import (
    QueryServiceLLMConfig,
    QueryServiceChatMessage,
    QueryServiceToolDefinition,
    QueryServiceToolCall,
    TokenUsage
)

class QueryAdvancePayload(BaseModel):
    """Payload for query.advance - advanced chat with tools support."""
    messages: List[QueryServiceChatMessage] = Field(
        ..., 
        description="Conversation history including system, user, assistant and tool messages"
    )
    agent_config: QueryServiceLLMConfig = Field(..., description="LLM configuration")
    tools: List[QueryServiceToolDefinition] = Field(
        ..., 
        description="List of tools available for the LLM"
    )
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(
        default="auto",
        description="Controls tool selection: 'none', 'auto', or specific tool"
    )

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        if not v:
            raise ValueError("At least one message is required")
        return v

    model_config = {"extra": "forbid"}

class QueryAdvanceResponseData(BaseModel):
    """Response data for query.advance."""
    message: QueryServiceChatMessage = Field(
        ..., 
        description="The assistant's response (may include tool_calls)"
    )
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage statistics")
    query_id: str = Field(..., description="Unique query ID")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}