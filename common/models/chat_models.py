"""
Modelos unificados para chat y embeddings basados en OpenAI y Groq SDKs.
Estos modelos son compartidos entre Agent Execution Service y Query Service.
"""
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# =============================================================================
# EMBEDDING MODELS (Basados en OpenAI Embeddings API)
# =============================================================================

class EmbeddingModel(str, Enum):
    """Modelos de embedding soportados."""
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"


class EmbeddingRequest(BaseModel):
    """Request para generar embeddings (compatible con OpenAI)."""
    model: EmbeddingModel = Field(default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
    input: Union[str, List[str]] = Field(..., description="Texto o lista de textos")
    dimensions: Optional[int] = Field(None, description="Dimensiones del vector (solo v3)")
    encoding_format: Literal["float", "base64"] = Field(default="float")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# CHAT MODELS (Basados en Groq Chat API)
# =============================================================================

class ChatModel(str, Enum):
    """Modelos de chat soportados en Groq."""
    LLAMA3_70B = "llama-3.3-70b-versatile"
    LLAMA3_8B = "llama-3.3-8b-instruct"
    MIXTRAL_8X7B = "mixtral-8x7b-32768"
    GEMMA_7B = "gemma-7b-it"


class ChatMessage(BaseModel):
    """Mensaje de chat (compatible con Groq/OpenAI)."""
    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="Rol del mensaje")
    content: Optional[str] = Field(None, description="Contenido del mensaje")
    name: Optional[str] = Field(None, description="Nombre para mensajes de tool")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Llamadas a herramientas")
    tool_call_id: Optional[str] = Field(None, description="ID de llamada a herramienta")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v, info):
        # Content es requerido excepto para assistant con tool_calls
        if v is None and info.data.get('role') == 'assistant' and not info.data.get('tool_calls'):
            raise ValueError("content es requerido cuando no hay tool_calls")
        return v
    
    model_config = {"extra": "forbid"}


class ChatCompletionRequest(BaseModel):
    """Request para chat completion (compatible con Groq)."""
    model: ChatModel = Field(default=ChatModel.LLAMA3_70B)
    messages: List[ChatMessage] = Field(..., min_items=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0) 
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop: Optional[Union[str, List[str]]] = Field(None, description="Secuencias de parada")
    
    # Campos para advance chat (tools)
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Herramientas disponibles")
    tool_choice: Optional[Union[Literal["none", "auto"], Dict[str, Any]]] = Field(None)
    
    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        # Debe haber al menos un mensaje system o user
        has_system = any(msg.role == "system" for msg in v)
        has_user = any(msg.role == "user" for msg in v)
        if not (has_system or has_user):
            raise ValueError("Debe haber al menos un mensaje system o user")
        return v
    
    model_config = {"extra": "forbid"}


# =============================================================================
# RAG SPECIFIC MODELS
# =============================================================================

class RAGSearchRequest(BaseModel):
    """Request para búsqueda RAG."""
    query: str = Field(..., min_length=1, description="Query de búsqueda")
    collection_ids: List[str] = Field(..., min_items=1, description="IDs de colecciones")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos específicos")
    top_k: int = Field(default=5, gt=0, le=20, description="Número de resultados")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    model_config = {"extra": "forbid"}


class RAGChunk(BaseModel):
    """Chunk de documento encontrado en búsqueda RAG."""
    chunk_id: str = Field(..., description="ID único del chunk")
    content: str = Field(..., description="Contenido del chunk")
    document_id: str = Field(..., description="ID del documento origen")
    collection_id: str = Field(..., description="ID de la colección")
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "forbid"}


# =============================================================================
# SIMPLE CHAT PAYLOAD (Unificado)
# =============================================================================

class SimpleChatPayload(BaseModel):
    """Payload unificado para simple chat con RAG automático."""
    # Mensaje principal
    user_message: str = Field(..., min_length=1)
    
    # Configuración de chat (compatible con Groq)
    chat_model: ChatModel = Field(default=ChatModel.LLAMA3_70B)
    system_prompt: str = Field(
        default="You are a helpful AI assistant. Use the provided context to answer questions accurately."
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop: Optional[List[str]] = None
    
    # Configuración de embeddings (compatible con OpenAI)
    embedding_model: EmbeddingModel = Field(default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
    embedding_dimensions: Optional[int] = None
    
    # Configuración de RAG
    collection_ids: List[str] = Field(..., min_items=1)
    document_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, gt=0, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Historial de conversación
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    
    @field_validator('conversation_history')
    @classmethod
    def validate_history(cls, v):
        if len(v) > 50:
            raise ValueError("Historial demasiado largo (máximo 50 mensajes)")
        # Solo permitir roles user y assistant en historial
        for msg in v:
            if msg.role not in ["user", "assistant"]:
                raise ValueError(f"Rol '{msg.role}' no permitido en historial")
        return v
    
    model_config = {"extra": "forbid"}


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class TokenUsage(BaseModel):
    """Uso de tokens (compatible con Groq/OpenAI)."""
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0) 
    total_tokens: int = Field(default=0)
    
    model_config = {"extra": "forbid"}


class SimpleChatResponse(BaseModel):
    """Respuesta unificada para simple chat."""
    message: str = Field(..., description="Respuesta del asistente")
    sources: List[str] = Field(default_factory=list, description="IDs de documentos usados")
    usage: TokenUsage = Field(..., description="Uso de tokens")
    query_id: str = Field(..., description="ID único de la consulta")
    conversation_id: str = Field(..., description="ID de la conversación")
    execution_time_ms: int = Field(..., description="Tiempo de ejecución")
    
    model_config = {"extra": "forbid"}


class ToolDefinition(BaseModel):
    """Representa una herramienta."""
    name: str = Field(..., description="Nombre de la herramienta")
    description: str = Field(..., description="Descripción de la herramienta")
    functions: List[Dict[str, Any]] = Field(..., description="Funciones disponibles")
    
    model_config = {"extra": "forbid"}


class ToolCall(BaseModel):
    """Representa una llamada a herramienta."""
    id: str = Field(..., description="ID único de la llamada")
    type: str = Field(default="function")
    function: Dict[str, Any] = Field(..., description="Función llamada y argumentos")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# ADVANCE CHAT PAYLOAD (Unificado)
# =============================================================================

class AdvanceChatPayload(BaseModel):
    """Payload unificado para advance chat con RAG y Tools."""
    # Mensaje principal
    user_message: str = Field(..., min_length=1)
    
    # Configuración de chat (compatible con Groq)
    chat_model: ChatModel = Field(default=ChatModel.LLAMA3_70B)
    system_prompt: str = Field(
        default="You are a helpful AI assistant. Use the provided context and tools to answer questions accurately."
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Campos para advance chat (tools)
    tools: Optional[List[ToolDefinition]] = Field(None, description="Herramientas disponibles")
    tool_choice: Optional[Union[Literal["none", "auto"], Dict[str, Any]]] = Field(None)
    
    # Configuración de RAG
    collection_ids: List[str] = Field(..., min_items=1)
    document_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, gt=0, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Historial de conversación
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    
    model_config = {"extra": "forbid"}


class AdvanceChatResponse(BaseModel):
    """Respuesta unificada para advance chat."""
    message: Optional[str] = Field(None, description="Respuesta del asistente (si la hay)")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="Llamadas a herramientas")
    sources: List[str] = Field(default_factory=list, description="IDs de documentos usados")
    usage: TokenUsage = Field(..., description="Uso de tokens")
    query_id: str = Field(..., description="ID único de la consulta")
    conversation_id: str = Field(..., description="ID de la conversación")
    execution_time_ms: int = Field(..., description="Tiempo de ejecución")
    
    model_config = {"extra": "forbid"}