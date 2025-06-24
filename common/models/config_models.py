"""
Modelos de configuración para los servicios del sistema.
Separa claramente las responsabilidades de configuración entre servicios.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class EmbeddingModel(str, Enum):
    """Modelos de embedding soportados."""
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"


class ChatModel(str, Enum):
    """Modelos de chat soportados en Groq."""
    LLAMA3_70B = "llama-3.3-70b-versatile"
    LLAMA3_8B = "llama-3.3-8b-instruct"
    MIXTRAL_8X7B = "mixtral-8x7b-32768"
    GEMMA_7B = "gemma-7b-it"


class ExecutionConfig(BaseModel):
    """
    Configuración para el Agent Execution Service.
    Controla el comportamiento del loop de ejecución del agente.
    """
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Número máximo de iteraciones del loop ReAct"
    )
    enable_history: bool = Field(
        default=True,
        description="Si mantener historial de conversación en cache"
    )
    history_ttl: int = Field(
        default=1800,
        ge=60,
        le=86400,
        description="TTL del historial en segundos (1-24 horas)"
    )
    tool_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout para ejecución de herramientas en segundos"
    )
    stream_response: bool = Field(
        default=False,
        description="Si hacer streaming de respuestas"
    )
    
    model_config = {"extra": "forbid"}


class QueryConfig(BaseModel):
    """
    Configuración para consultas LLM (Groq).
    Contiene todos los parámetros necesarios para llamadas al modelo.
    """
    model: ChatModel = Field(
        ...,
        description="Modelo a usar"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Control de creatividad del modelo"
    )
    max_tokens: int = Field(
        default=2048,
        gt=0,
        le=8192,
        description="Máximo de tokens en respuesta"
    )
    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter"
    )
    frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Penalización de frecuencia"
    )
    presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Penalización de presencia"
    )
    stop: Optional[List[str]] = Field(
        default=None,
        description="Secuencias de parada opcionales"
    )
    system_prompt_template: str = Field(
        ...,
        description="Template para system prompt en RAG (obligatorio para agentes)"
    )
    max_context_tokens: int = Field(
        default=4000,
        gt=0,
        le=32768,
        description="Límite de tokens de contexto para RAG"
    )
    enable_parallel_search: bool = Field(
        default=True,
        description="Habilitar búsquedas paralelas en colecciones"
    )
    
    model_config = {"extra": "forbid"}


class RAGConfig(BaseModel):
    """
    Configuración para búsqueda RAG.
    Define parámetros para la recuperación de información.
    """
    collection_ids: List[str] = Field(
        ...,
        min_items=1,
        description="IDs de colecciones a buscar"
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="IDs de documentos específicos (opcional)"
    )
    top_k: int = Field(
        default=5,
        gt=0,
        le=20,
        description="Número de resultados más relevantes"
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Umbral mínimo de similitud"
    )
    embedding_model: EmbeddingModel = Field(
        default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL,
        description="Modelo de embeddings a utilizar"
    )
    embedding_dimensions: Optional[int] = Field(
        default=None,
        description="Dimensiones del vector (auto si None)"
    )
    
    model_config = {"extra": "forbid"}
