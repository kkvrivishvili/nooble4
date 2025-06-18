"""
Modelos Pydantic para los payloads de las acciones del Query Service.

Estos modelos definen la estructura esperada del campo 'data' en DomainAction
para cada tipo de acción que maneja el servicio.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

# --- Modelos de Request (para action.data) ---

class QueryGeneratePayload(BaseModel):
    """Payload para acción query.generate - Procesamiento RAG completo."""
    
    query_text: str = Field(..., description="Texto de la consulta en lenguaje natural")
    collection_ids: List[str] = Field(..., description="IDs de las colecciones donde buscar")
    
    # Parámetros opcionales de búsqueda
    top_k: Optional[int] = Field(None, description="Número de resultados a recuperar")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Umbral mínimo de similitud")
    
    # Parámetros opcionales de generación
    llm_model: Optional[str] = Field(None, description="Modelo LLM específico a usar")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperatura para generación")
    max_tokens: Optional[int] = Field(None, ge=1, description="Máximo de tokens en la respuesta")
    system_prompt: Optional[str] = Field(None, description="Prompt de sistema personalizado")
    
    # Contexto adicional
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list,
        description="Historial de conversación para contexto"
    )
    
    @field_validator('collection_ids')
    @classmethod
    def validate_collection_ids(cls, v):
        if not v:
            raise ValueError("Al menos una collection_id es requerida")
        return v


class QuerySearchPayload(BaseModel):
    """Payload para acción query.search - Solo búsqueda vectorial."""
    
    query_text: str = Field(..., description="Texto de búsqueda")
    collection_ids: List[str] = Field(..., description="IDs de las colecciones donde buscar")
    
    # Parámetros de búsqueda
    top_k: Optional[int] = Field(None, description="Número de resultados")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Filtros adicionales
    filters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Filtros adicionales para la búsqueda"
    )


class QueryStatusPayload(BaseModel):
    """Payload para acción query.status - Consultar estado."""
    
    query_id: str = Field(..., description="ID de la consulta a verificar")


# --- Modelos de Response (para DomainActionResponse.data o callbacks) ---

class SearchResult(BaseModel):
    """Representa un resultado individual de búsqueda."""
    
    chunk_id: str = Field(..., description="ID único del chunk")
    content: str = Field(..., description="Contenido del chunk")
    similarity_score: float = Field(..., description="Score de similitud (0-1)")
    
    # Metadatos del documento
    document_id: str = Field(..., description="ID del documento origen")
    document_title: Optional[str] = Field(None, description="Título del documento")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)
    

class QueryGenerateResponse(BaseModel):
    """Respuesta para query.generate."""
    
    query_id: str = Field(..., description="ID único de la consulta")
    query_text: str = Field(..., description="Texto original de la consulta")
    
    # Respuesta generada
    generated_response: str = Field(..., description="Respuesta generada por el LLM")
    
    # Contexto utilizado
    search_results: List[SearchResult] = Field(
        ..., 
        description="Chunks recuperados y utilizados para la generación"
    )
    
    # Metadatos de generación
    llm_model: str = Field(..., description="Modelo LLM utilizado")
    temperature: float = Field(..., description="Temperatura usada")
    prompt_tokens: Optional[int] = Field(None, description="Tokens en el prompt")
    completion_tokens: Optional[int] = Field(None, description="Tokens en la respuesta")
    total_tokens: Optional[int] = Field(None, description="Total de tokens")
    
    # Timing
    search_time_ms: int = Field(..., description="Tiempo de búsqueda en ms")
    generation_time_ms: int = Field(..., description="Tiempo de generación en ms")
    total_time_ms: int = Field(..., description="Tiempo total en ms")
    
    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QuerySearchResponse(BaseModel):
    """Respuesta para query.search."""
    
    query_id: str = Field(..., description="ID único de la búsqueda")
    query_text: str = Field(..., description="Texto de búsqueda original")
    
    # Resultados
    search_results: List[SearchResult] = Field(..., description="Resultados encontrados")
    total_results: int = Field(..., description="Total de resultados encontrados")
    
    # Timing
    search_time_ms: int = Field(..., description="Tiempo de búsqueda en ms")
    
    # Metadatos
    collections_searched: List[str] = Field(..., description="Colecciones consultadas")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryErrorResponse(BaseModel):
    """Respuesta de error para cualquier acción de query."""
    
    query_id: Optional[str] = Field(None, description="ID de la consulta si está disponible")
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detalles adicionales del error")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Modelos internos para comunicación con otros servicios ---

class EmbeddingRequest(BaseModel):
    """Request para solicitar embeddings al Embedding Service."""
    
    texts: List[str] = Field(..., description="Textos para generar embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding específico")
    

class CollectionConfig(BaseModel):
    """Configuración de una colección."""
    
    collection_id: str
    collection_name: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    metadata: Dict[str, Any] = Field(default_factory=dict)