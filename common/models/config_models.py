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
    Configuración para el comportamiento del Agent Execution Service.
    
    Controla aspectos como cache, timeouts, iteraciones del loop ReAct, etc.
    """
    # Cache y historial
    history_ttl: int = Field(
        default=3600,
        gt=0,
        description="TTL en segundos para el historial de conversación"
    )
    enable_history_cache: bool = Field(
        default=True,
        description="Habilitar caché de historial de conversación"
    )
    max_history_length: int = Field(
        default=50,
        gt=0,
        le=200,
        description="Número máximo de mensajes en historial de conversación"
    )
    
    # Timeouts y límites operacionales
    tool_timeout: int = Field(
        default=30,
        gt=0,
        description="Timeout en segundos para ejecución de herramientas"
    )
    max_iterations: int = Field(
        default=10,
        gt=0,
        le=20,
        description="Máximo de iteraciones para el loop ReAct"
    )
    
    model_config = {"extra": "forbid"}


class QueryConfig(BaseModel):
    """
    Configuración para consultas LLM (Groq).
    Contiene todos los parámetros necesarios para llamadas al modelo.
    
    También incluye configuración para el SDK de Groq (timeout, max_retries).    
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
    
    # Configuración específica del SDK de Groq
    timeout: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Timeout en segundos para la API de Groq (None usa el valor por defecto del servicio)"
    )
    max_retries: Optional[int] = Field(
        default=None, 
        ge=0,
        description="Número máximo de reintentos para la API de Groq (None usa el valor por defecto del servicio)"
    )
    
    model_config = {"extra": "forbid"}


class RAGConfig(BaseModel):
    """
    Configuración para operaciones RAG (Retrieval-Augmented Generation).
    
    Define parámetros para búsqueda vectorial y generación de embeddings.
    """
    # Configuración de colecciones y documentos
    collection_ids: List[str] = Field(
        ...,
        min_items=1,
        description="IDs de colecciones a buscar"
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="IDs de documentos específicos (opcional)"
    )
    
    # Configuración de embeddings
    embedding_model: EmbeddingModel = Field(
        default=EmbeddingModel.TEXT_EMBEDDING_3_SMALL,
        description="Modelo para generar embeddings"
    )
    embedding_dimensions: int = Field(
        default=1536,
        gt=0,
        description="Dimensiones del vector de embedding"
    )
    encoding_format: str = Field(
        default="float",
        description="Formato de codificación para embeddings (float, base64)"
    )
    
    # Configuración de búsqueda
    top_k: int = Field(
        default=5,
        gt=0,
        le=20,
        description="Número de documentos más relevantes a recuperar"
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Umbral mínimo de similitud para considerar un documento relevante"
    )
    
    # Configuración específica del SDK de OpenAI
    timeout: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Timeout en segundos para la API de OpenAI (None usa el valor por defecto del servicio)"
    )
    max_retries: Optional[int] = Field(
        default=None, 
        ge=0,
        description="Número máximo de reintentos para la API de OpenAI (None usa el valor por defecto del servicio)"
    )
    max_text_length: Optional[int] = Field(
        default=None,
        description="Longitud máxima del texto para el embedding, si se requiere truncamiento."
    )
    
    model_config = {"extra": "forbid"}
