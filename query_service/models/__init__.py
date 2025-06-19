"""
Models for Query Service Interface.

This package defines the Pydantic models used for communication with the Query Service,
structured into base reusable models and specific payloads for different actions.
"""

from .base_models import (
    ACTION_QUERY_GENERATE,
    ACTION_QUERY_LLM_DIRECT,
    ACTION_QUERY_SEARCH,
    ACTION_QUERY_STATUS,
    QueryServiceLLMProvider,
    QueryServiceLLMConfig,
    QueryServiceChatMessage,
    QueryServiceToolFunctionParameters,
    QueryServiceToolFunction,
    QueryServiceToolDefinition,
    RetrievedDoc,
    QueryErrorResponseData,
    TokenUsage
)
from .generate_payloads import (
    QueryGeneratePayload,
    QueryGenerateResponseData
)
from .llm_direct_payloads import (
    QueryLLMDirectPayload,
    QueryLLMDirectResponseData
)
from .search_payloads import (
    QuerySearchPayload,
    QuerySearchResponseData
)
from .status_payloads import (
    QueryStatusPayload,
    QueryStatusResponseData
)

__all__ = [
    # Action Constants
    "ACTION_QUERY_GENERATE",
    "ACTION_QUERY_LLM_DIRECT",
    "ACTION_QUERY_SEARCH",
    "ACTION_QUERY_STATUS",
    
    # Base Models
    "QueryServiceLLMProvider",
    "QueryServiceLLMConfig",
    "QueryServiceChatMessage",
    "QueryServiceToolFunctionParameters",
    "QueryServiceToolFunction",
    "QueryServiceToolDefinition",
    "RetrievedDoc",
    "QueryErrorResponseData",
    "TokenUsage",
    
    # Generate Payloads
    "QueryGeneratePayload",
    "QueryGenerateResponseData",
    
    # LLM Direct Payloads
    "QueryLLMDirectPayload",
    "QueryLLMDirectResponseData",
    
    # Search Payloads
    "QuerySearchPayload",
    "QuerySearchResponseData",
    
    # Status Payloads
    "QueryStatusPayload",
    "QueryStatusResponseData",
]