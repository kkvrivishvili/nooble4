"""
Modelos de Domain Actions para el servicio de embeddings.
MODIFICADO: Integración con ExecutionContext y sistema de colas por tier.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import Field, validator

from common.models.actions import DomainAction


class EmbeddingGenerateAction(DomainAction):
    """
    Domain Action para generar embeddings.
    MODIFICADO: Usar ExecutionContext del DomainAction base.
    """
    
    action_type: str = "embedding.generate"
    
    # MODIFICADO: Ya no necesitamos campos específicos de contexto
    # porque execution_context viene en DomainAction base
    
    # Configuración para generación de embedding
    texts: List[str] = Field(..., description="Textos para procesar")
    model: Optional[str] = Field(None, description="Modelo de embedding a usar")
    
    # Metadatos opcionales
    collection_id: Optional[UUID] = Field(None, description="ID de colección")
    chunk_ids: Optional[List[str]] = Field(None, description="IDs de chunks")
    
    @validator("texts")
    def validate_texts(cls, v):
        if not v:
            raise ValueError("Se requiere al menos un texto")
        return v
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "generate"


class EmbeddingValidateAction(DomainAction):
    """
    Domain Action para validar textos.
    MODIFICADO: Usar ExecutionContext del DomainAction base.
    """
    
    action_type: str = "embedding.validate"
    
    texts: List[str] = Field(..., description="Textos a validar")
    model: Optional[str] = Field(None, description="Modelo para validar contra")
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "validate"


class EmbeddingCallbackAction(DomainAction):
    """
    Domain Action para callbacks de embeddings.
    MODIFICADO: Integración con sistema de callbacks por tier.
    """
    
    action_type: str = "embedding.callback"
    
    # Estado de la operación
    status: str = Field("completed", description="Estado: completed, failed")
    
    # Resultado de la operación
    embeddings: List[List[float]] = Field(..., description="Vectores generados")
    model: str = Field(..., description="Modelo usado")
    dimensions: int = Field(..., description="Dimensiones de los vectores")
    total_tokens: int = Field(..., description="Tokens consumidos")
    
    # NUEVO: Métricas de performance
    processing_time: float = Field(..., description="Tiempo de procesamiento")
    
    # Datos de error (si aplica)
    error: Optional[Dict[str, Any]] = Field(None, description="Información de error si falló")
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "callback"