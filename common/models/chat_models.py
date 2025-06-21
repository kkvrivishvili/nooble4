"""
Modelos unificados para chat y embeddings compatibles con OpenAI y Groq SDKs.
Simplificados para uso directo sin transformaciones.
"""
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ChatModel(str, Enum):
    """Modelos de chat soportados en Groq."""
    LLAMA3_70B = "llama-3.3-70b-versatile"
    LLAMA3_8B = "llama-3.3-8b-instruct"
    MIXTRAL_8X7B = "mixtral-8x7b-32768"
    GEMMA_7B = "gemma-7b-it"


class EmbeddingModel(str, Enum):
    """Modelos de embedding soportados."""
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"


# =============================================================================
# CORE MODELS (Compatible con SDKs)
# =============================================================================

class ChatMessage(BaseModel):
    """
    Mensaje de chat compatible con Groq/OpenAI.
    Estructura directa para usar con SDKs sin transformación.
    """
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="Rol del mensaje")
    content: Optional[str] = Field(None, description="Contenido del mensaje")
    
    # Para tool calls (formato Groq/OpenAI)
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Llamadas a herramientas")
    tool_call_id: Optional[str] = Field(None, description="ID de llamada a herramienta")
    
    # Nombre opcional para mensajes de tool
    name: Optional[str] = Field(None, description="Nombre para mensajes de tool")
    
    model_config = {"extra": "forbid"}


class TokenUsage(BaseModel):
    """Uso de tokens (formato estándar OpenAI/Groq)."""
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    
    model_config = {"extra": "forbid"}


# =============================================================================
# UNIFIED REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """
    Request unificado para chat (simple y avanzado).
    Compatible directamente con Groq API.
    """
    # Mensajes de la conversación
    messages: List[ChatMessage] = Field(..., min_items=1, description="Mensajes de la conversación")
    
    # Configuración del modelo
    model: ChatModel = Field(default=ChatModel.LLAMA3_70B, description="Modelo a usar")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop: Optional[Union[str, List[str]]] = Field(None, description="Secuencias de parada")
    
    # Para chat avanzado (tools)
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Herramientas disponibles (formato Groq)")
    tool_choice: Optional[Union[Literal["none", "auto"], Dict[str, Any]]] = Field(None)
    
    # Para RAG (cuando aplique)
    rag_config: Optional["RAGConfig"] = Field(None, description="Configuración RAG si se necesita búsqueda")
    
    # Metadata
    conversation_id: Optional[str] = Field(None, description="ID de conversación para tracking")
    
    model_config = {"extra": "forbid"}


class ChatResponse(BaseModel):
    """
    Response unificado para chat.
    Estructura simple y directa.
    """
    message: ChatMessage = Field(..., description="Mensaje de respuesta del asistente")
    usage: TokenUsage = Field(..., description="Uso de tokens")
    
    # Metadata
    conversation_id: str = Field(..., description="ID de la conversación")
    execution_time_ms: int = Field(..., description="Tiempo de ejecución")
    
    # Para RAG
    sources: List[str] = Field(default_factory=list, description="IDs de documentos usados")
    
    # Para ReAct
    iterations: Optional[int] = Field(None, description="Número de iteraciones ReAct (solo avanzado)")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# RAG SPECIFIC
# =============================================================================

class RAGConfig(BaseModel):
    """Configuración para búsqueda RAG."""
    collection_ids: List[str] = Field(..., min_items=1, description="IDs de colecciones")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos específicos")
    top_k: int = Field(default=5, gt=0, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Configuración de embeddings
    embedding_model: EmbeddingModel = Field(default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
    embedding_dimensions: Optional[int] = Field(None)
    
    model_config = {"extra": "forbid"}


class RAGChunk(BaseModel):
    """Chunk encontrado en búsqueda RAG."""
    chunk_id: str
    content: str
    document_id: str
    collection_id: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "forbid"}


class RAGSearchResult(BaseModel):
    """Resultado de búsqueda RAG."""
    chunks: List[RAGChunk]
    total_found: int
    search_time_ms: int
    
    model_config = {"extra": "forbid"}


# =============================================================================
# EMBEDDING MODELS (Compatible con OpenAI)
# =============================================================================

class EmbeddingRequest(BaseModel):
    """Request para embeddings (compatible con OpenAI)."""
    input: Union[str, List[str]] = Field(..., description="Texto o lista de textos")
    model: EmbeddingModel = Field(default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
    dimensions: Optional[int] = Field(None, description="Dimensiones del vector (solo v3)")
    encoding_format: Literal["float", "base64"] = Field(default="float")
    
    model_config = {"extra": "forbid"}


class EmbeddingResponse(BaseModel):
    """Response de embeddings."""
    embeddings: List[List[float]] = Field(..., description="Vectores de embedding")
    model: str = Field(..., description="Modelo usado")
    dimensions: int = Field(..., description="Dimensiones de los vectores")
    usage: TokenUsage = Field(..., description="Uso de tokens")
    
    model_config = {"extra": "forbid"}

# =============================================================================
# CONVERSATION HISTORY
# =============================================================================

class ConversationHistory(BaseModel):
    """
    Historial de conversación compatible con OpenAI/Groq.
    Mantiene máximo 5 mensajes para optimizar tokens.
    """
    conversation_id: str = Field(..., description="ID único de la conversación")
    tenant_id: str = Field(..., description="ID del tenant")
    session_id: str = Field(..., description="ID de la sesión")
    agent_id: str = Field(..., description="ID del agente")
    messages: List[ChatMessage] = Field(
        default_factory=list, 
        description="Mensajes de la conversación (máximo 5)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_messages: int = Field(default=0, description="Contador total de mensajes")
    
    def add_message(self, message: ChatMessage) -> None:
        """Agrega mensaje manteniendo máximo 5."""
        self.messages.append(message)
        self.total_messages += 1
        if len(self.messages) > 5:
            self.messages.pop(0)  # Eliminar el más antiguo
        self.updated_at = datetime.now(timezone.utc)
    
    def to_chat_messages(self) -> List[ChatMessage]:
        """Retorna los mensajes en formato listo para ChatRequest."""
        return self.messages.copy()
    
    model_config = {"extra": "forbid"}