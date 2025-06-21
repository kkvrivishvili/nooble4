"""
Modelos específicos del Query Service que no están en common.
Solo mantiene SearchResult para el VectorClient.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """
    Resultado de búsqueda del vector store.
    Usado internamente por VectorClient.
    """
    chunk_id: str = Field(..., description="ID único del chunk")
    content: str = Field(..., description="Contenido del chunk")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Score de similitud")
    collection_id: str = Field(..., description="ID de la colección")
    document_id: Optional[str] = Field(None, description="ID del documento origen")
    document_title: Optional[str] = Field(None, description="Título del documento")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata adicional")
    
    model_config = {"extra": "forbid"}