"""
Modelos de Domain Actions para el servicio de embeddings.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from common.models.actions import DomainAction


class EmbeddingGenerateAction(DomainAction):
    """
    Acción para generar embeddings de uno o varios textos.
    """
    
    # Definición del tipo de acción
    action_type: str = "embedding.generate"
    
    # Configuración para generación de embedding
    texts: List[str]  # Textos para procesar (single o batch)
    model: Optional[str] = None  # Modelo de embedding a usar (usa default si no se especifica)
    
    # Metadatos opcionales
    collection_id: Optional[UUID] = None  # ID de colección (para tracking)
    chunk_ids: Optional[List[str]] = None  # IDs de chunks (para tracking)
    metadata: Optional[Dict[str, Any]] = None  # Metadatos adicionales

    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "client123",
                "session_id": "sess_abc123",
                "texts": ["Este es un texto de ejemplo para generar embedding"],
                "model": "text-embedding-3-small",
                "callback_queue": "agent.execution.callbacks"
            }
        }


class EmbeddingValidateAction(DomainAction):
    """
    Acción para validar textos antes de generar embeddings.
    Útil para verificar límites de tokens, tamaño de batch, etc.
    """
    
    action_type: str = "embedding.validate"
    
    texts: List[str]  # Textos a validar
    model: Optional[str] = None  # Modelo para validar contra sus límites

    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "client123",
                "session_id": "sess_abc123",
                "texts": ["Texto 1", "Texto 2", "Texto 3"],
                "model": "text-embedding-3-small",
                "callback_queue": "agent.execution.callbacks"
            }
        }


class EmbeddingCallbackAction(DomainAction):
    """
    Acción de callback con resultados de embeddings generados.
    """
    
    action_type: str = "embedding.callback"
    
    # Resultado de la operación
    embeddings: List[List[float]]  # Vectores generados
    model: str  # Modelo usado
    dimensions: int  # Dimensiones de los vectores
    total_tokens: int  # Tokens consumidos
    processing_time: float  # Tiempo de procesamiento en segundos
    
    # Referencias a la solicitud original
    task_id: str  # ID de tarea (mantiene trazabilidad)
    status: str = "completed"  # Estado del proceso
    error: Optional[Dict[str, Any]] = None  # Información de error si falló

    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "client123",
                "session_id": "sess_abc123",
                "embeddings": [[0.1, 0.2, 0.3, 0.4]],
                "model": "text-embedding-3-small",
                "dimensions": 1536,
                "total_tokens": 5,
                "processing_time": 0.45,
                "task_id": "task_xyz789",
                "status": "completed"
            }
        }
