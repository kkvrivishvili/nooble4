"""
Modelos específicos del Embedding Service para procesamiento por lotes.
Los modelos principales (EmbeddingRequest/Response) vienen de common.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# =============================================================================
# BATCH PROCESSING MODELS (Específicos del servicio)
# =============================================================================

class EmbeddingBatchPayload(BaseModel):
    """Payload para embedding.batch_process - Procesamiento por lotes."""
    
    texts: List[str] = Field(..., description="Lista de textos del lote")
    model: str = Field(..., description="Modelo de embedding a utilizar. Este campo es obligatorio.")
    dimensions: Optional[int] = Field(None, description="Dimensiones del vector")
    
    # Campos para propagar desde ingestion_service
    chunk_ids: Optional[List[str]] = Field(None, description="IDs de los chunks originales")
    collection_id: Optional[UUID] = Field(None, description="ID de la colección")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata original")
    
    model_config = {"extra": "forbid"}


class EmbeddingBatchResult(BaseModel):
    """Resultado de un batch de embeddings."""
    
    chunk_ids: List[str] = Field(..., description="IDs de chunks en el mismo orden que embeddings")
    embeddings: List[List[float]] = Field(..., description="Vectores de embedding generados")
    model: str = Field(..., description="Modelo utilizado")
    dimensions: int = Field(..., description="Dimensiones de los embeddings")
    
    # Métricas
    total_tokens: int = Field(..., description="Total de tokens procesados")
    processing_time_ms: int = Field(..., description="Tiempo de procesamiento")
    
    # Estado
    status: str = Field(..., description="Estado: 'completed', 'partial', 'failed'")
    failed_indices: List[int] = Field(default_factory=list, description="Índices de textos que fallaron")
    
    # Metadata original
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"extra": "forbid"}