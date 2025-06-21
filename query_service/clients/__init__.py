"""
Models for Query Service Interface.
"""
from .base_models import (
    ACTION_QUERY_SIMPLE,
    ACTION_QUERY_ADVANCE,
    ACTION_QUERY_RAG,
)

from .payloads import SearchResult

# Todos los demás modelos vienen de common
from common.models.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatModel,
    EmbeddingModel,
    EmbeddingRequest,
    EmbeddingResponse,
    RAGConfig,
    RAGChunk,
    RAGSearchResult,
    TokenUsage
)

__all__ = [
    # Action Constants
    "ACTION_QUERY_SIMPLE",
    "ACTION_QUERY_ADVANCE", 
    "ACTION_QUERY_RAG",
    
    # Local model
    "SearchResult",
    
    # Models from common
    "ChatRequest",
    "ChatResponse",
    "ChatMessage",
    "ChatModel",
    "EmbeddingModel",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "RAGConfig",
    "RAGChunk",
    "RAGSearchResult",
    "TokenUsage"
]