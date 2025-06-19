"""
Modelos Pydantic para payloads entrantes del Agent Execution Service.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class OperationMode(str, Enum):
    """Modos de operación soportados."""
    SIMPLE = "simple"
    ADVANCE = "advance"


class AgentConfig(BaseModel):
    """Configuración del agente LLM."""
    provider: str = Field(default="groq", description="Proveedor LLM")
    model: str = Field(default="llama-3.3-70b-versatile", description="Modelo LLM")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop_sequences: Optional[List[str]] = None

    model_config = {"extra": "allow"}  # Permitir campos adicionales de Groq


class EmbeddingConfig(BaseModel):
    """Configuración para embeddings."""
    provider: str = Field(default="openai", description="Proveedor de embeddings")
    model: str = Field(default="text-embedding-3-small", description="Modelo de embeddings")
    dimensions: Optional[int] = Field(default=1536, description="Dimensiones del vector")

    model_config = {"extra": "allow"}


class ToolDefinition(BaseModel):
    """Definición de una herramienta."""
    name: str = Field(..., description="Nombre de la herramienta")
    description: str = Field(..., description="Descripción de la herramienta")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Schema de parámetros")

    model_config = {"extra": "forbid"}


class SimpleChatPayload(BaseModel):
    """Payload para execution.chat.simple."""
    operation_mode: OperationMode = Field(OperationMode.SIMPLE)
    user_message: str = Field(..., min_length=1, description="Mensaje del usuario")
    collection_ids: List[str] = Field(..., min_items=1, description="IDs de colecciones (obligatorio)")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos (opcional)")
    agent_config: AgentConfig = Field(..., description="Configuración del agente")
    embedding_config: EmbeddingConfig = Field(..., description="Configuración de embeddings")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list, 
        description="Historial de conversación"
    )

    @field_validator('conversation_history')
    @classmethod
    def validate_history(cls, v):
        if v and len(v) > 50:
            raise ValueError("Historial demasiado largo (máximo 50 mensajes)")
        return v


class AdvanceChatPayload(BaseModel):
    """Payload para execution.chat.advance."""
    operation_mode: OperationMode = Field(OperationMode.ADVANCE)
    user_message: str = Field(..., min_length=1, description="Mensaje del usuario")
    collection_ids: List[str] = Field(..., min_items=1, description="IDs de colecciones (obligatorio)")
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos (opcional)")
    agent_config: AgentConfig = Field(..., description="Configuración del agente")
    embedding_config: EmbeddingConfig = Field(..., description="Configuración de embeddings")
    tools: List[ToolDefinition] = Field(..., min_items=1, description="Herramientas disponibles")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list, 
        description="Historial de conversación"
    )
    max_iterations: int = Field(default=10, gt=0, le=20, description="Máximo de iteraciones ReAct")

    @field_validator('tools')
    @classmethod
    def validate_tools(cls, v):
        # Asegurar que siempre existe la tool "knowledge"
        tool_names = [tool.name for tool in v]
        if "knowledge" not in tool_names:
            # Agregar knowledge tool si no está presente
            knowledge_tool = ToolDefinition(
                name="knowledge",
                description="Search relevant information from knowledge base",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        }
                    },
                    "required": ["query"]
                }
            )
            v.append(knowledge_tool)
        return v