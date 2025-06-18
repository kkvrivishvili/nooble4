"""
Modelos Pydantic para los payloads de las acciones del Embedding Service.

Estos modelos definen la estructura esperada del campo 'data' en DomainAction
para cada tipo de acción que maneja el servicio.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID

# --- Modelos de Request (para action.data) ---

class EmbeddingGeneratePayload(BaseModel):
    """Payload para acción embedding.generate - Generación de embeddings."""
    
    texts: List[str] = Field(..., description="Lista de textos para generar embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding específico a usar")
    
    # Opciones adicionales
    dimensions: Optional[int] = Field(None, description="Dimensiones del embedding (si el modelo lo soporta)")
    encoding_format: Optional[str] = Field("float", description="Formato de codificación: 'float' o 'base64'")
    
    # Metadatos para tracking
    collection_id: Optional[UUID] = Field(None, description="ID de la colección asociada")
    chunk_ids: Optional[List[str]] = Field(None, description="IDs de los chunks correspondientes")
    
    @field_validator('texts')
    @classmethod
    def validate_texts(cls, v):
        if not v:
            raise ValueError("La lista de textos no puede estar vacía")
        if len(v) > 100:  # Límite básico para evitar sobrecarga
            raise ValueError("No se pueden procesar más de 100 textos a la vez")
        return v


class EmbeddingGenerateQueryPayload(BaseModel):
    """Payload para embedding.generate_query - Embedding de consulta única."""
    
    texts: List[str] = Field(..., description="Lista con un único texto de consulta", max_length=1)
    model: Optional[str] = Field(None, description="Modelo de embedding específico")
    
    @field_validator('texts')
    @classmethod
    def validate_single_text(cls, v):
        if not v or len(v) != 1:
            raise ValueError("Se requiere exactamente un texto para generate_query")
        return v


class EmbeddingBatchPayload(BaseModel):
    """Payload para embedding.batch_process - Procesamiento por lotes."""
    
    batch_id: str = Field(..., description="ID único del lote")
    texts: List[str] = Field(..., description="Lista de textos del lote")
    model: Optional[str] = Field(None, description="Modelo de embedding")
    
    # Metadatos del lote
    collection_id: Optional[UUID] = Field(None)
    document_ids: Optional[List[str]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingValidatePayload(BaseModel):
    """Payload para embedding.validate - Validación de capacidad."""
    
    texts: List[str] = Field(..., description="Textos a validar")
    model: Optional[str] = Field(None, description="Modelo a validar")


# --- Modelos de Response (para DomainActionResponse.data o callbacks) ---

class EmbeddingResult(BaseModel):
    """Representa un embedding individual."""
    
    text_index: int = Field(..., description="Índice del texto original")
    embedding: List[float] = Field(..., description="Vector de embedding")
    dimensions: int = Field(..., description="Dimensiones del vector")
    

class EmbeddingResponse(BaseModel):
    """Respuesta para embedding.generate."""
    
    embeddings: List[List[float]] = Field(..., description="Lista de embeddings generados")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones de los embeddings")
    
    # Métricas
    total_tokens: int = Field(..., description="Total de tokens procesados")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento en ms")
    
    # Metadatos
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingQueryResponse(BaseModel):
    """Respuesta para embedding.generate_query."""
    
    embedding: List[float] = Field(..., description="Embedding del texto de consulta")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones del embedding")
    
    # Métricas
    tokens: int = Field(..., description="Tokens en el texto")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingBatchResponse(BaseModel):
    """Respuesta para embedding.batch_process."""
    
    batch_id: str = Field(..., description="ID del lote procesado")
    status: str = Field(..., description="Estado: 'completed', 'partial', 'failed'")
    
    # Resultados
    embeddings: List[EmbeddingResult] = Field(..., description="Embeddings procesados")
    successful_count: int = Field(..., description="Número de embeddings exitosos")
    failed_count: int = Field(..., description="Número de embeddings fallidos")
    
    # Métricas
    total_tokens: int = Field(0)
    processing_time_ms: int = Field(...)
    
    # Errores si los hay
    errors: Optional[List[Dict[str, Any]]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmbeddingValidationResponse(BaseModel):
    """Respuesta para embedding.validate."""
    
    is_valid: bool = Field(..., description="Si la solicitud es válida")
    can_process: bool = Field(..., description="Si el servicio puede procesarla")
    
    # Detalles de validación
    text_count: int = Field(..., description="Número de textos")
    estimated_tokens: int = Field(..., description="Tokens estimados")
    model_available: bool = Field(..., description="Si el modelo está disponible")
    
    # Mensajes
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EmbeddingErrorResponse(BaseModel):
    """Respuesta de error para cualquier acción de embedding."""
    
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    error_details: Optional[Dict[str, Any]] = Field(None)
    
    # Contexto
    action_type: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    text_count: Optional[int] = Field(None)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingMetrics(BaseModel):
    """Métricas de uso de embeddings."""
    
    tenant_id: str
    date: str
    
    # Contadores
    total_requests: int = Field(0)
    total_texts: int = Field(0)
    total_tokens: int = Field(0)
    
    # Performance
    avg_processing_time_ms: float = Field(0.0)
    avg_texts_per_request: float = Field(0.0)
    
    # Por modelo
    usage_by_model: Dict[str, int] = Field(default_factory=dict)