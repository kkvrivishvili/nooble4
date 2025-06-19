"""
Models for Query Service Interface.
"""
from .base_models import (
    ACTION_QUERY_SIMPLE,
    ACTION_QUERY_ADVANCE,
    ACTION_QUERY_RAG,
)

# Importar modelos compartidos
from common.models.chat_models import (
    SimpleChatPayload,
    SimpleChatResponse,
    ChatMessage,
    ChatCompletionRequest,
    EmbeddingRequest,
    TokenUsage,
    RAGChunk,
    ChatModel,
    EmbeddingModel
)

__all__ = [
    # Action Constants
    "ACTION_QUERY_SIMPLE",
    "ACTION_QUERY_ADVANCE", 
    "ACTION_QUERY_RAG",
    
    # Shared Models
    "SimpleChatPayload",
    "SimpleChatResponse",
    "ChatMessage",
    "ChatCompletionRequest",
    "EmbeddingRequest",
    "TokenUsage",
    "RAGChunk",
    "ChatModel",
    "EmbeddingModel"
]