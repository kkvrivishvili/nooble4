"""
Pydantic models for the 'query.advance' action (advanced chat with tools).
"""
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

from common.models.chat_models import (
    AgentConfig,  # Replaces QueryServiceLLMConfig
    ChatMessage,  # Replaces QueryServiceChatMessage
    ToolDefinition,  # Replaces QueryServiceToolDefinition
    ToolCall,  # Replaces QueryServiceToolCall
    TokenUsage
)

class QueryAdvancePayload(BaseModel):
    """Payload for query.advance - advanced chat with tools support."""
    messages: List[ChatMessage] = Field(
        ..., 
        description="Conversation history including system, user, assistant and tool messages"
    )
    agent_config: AgentConfig = Field(..., description="LLM configuration from common models")
    tools: List[ToolDefinition] = Field(
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
    message: ChatMessage = Field(
        ..., 
        description="The assistant's response (may include tool_calls)"
    )
    finish_reason: str = Field(..., description="Reason for completion")
    usage: TokenUsage = Field(..., description="Token usage statistics from common models")
    query_id: str = Field(..., description="Unique query ID")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"extra": "forbid"}