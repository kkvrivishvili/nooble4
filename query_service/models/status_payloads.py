"""
Pydantic models for the 'query.status' action.
"""
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Payload for ACTION_QUERY_STATUS --- #

class QueryStatusPayload(BaseModel):
    """Payload for action query.status - Consultar estado de una consulta previa."""
    query_id: str = Field(..., description="ID de la consulta original a verificar (e.g., de un query.generate o query.llm.direct previo)")

    model_config = {"extra": "forbid"}


class QueryStatusResponseData(BaseModel):
    """Response data for query.status action."""
    query_id: str = Field(..., description="ID de la consulta original.")
    status: Literal["pending", "in_progress", "completed", "failed", "not_found"] = Field(
        ..., 
        description="Estado actual de la consulta."
    )
    action_type: Optional[str] = Field(None, description="Tipo de acción original (e.g., 'query.generate', 'query.llm.direct').")
    # Potentially include a snippet of the result or error if completed/failed
    result_preview: Optional[Dict[str, Any]] = Field(None, description="Breve resumen o vista previa del resultado si está completado.")
    error_info: Optional[Dict[str, Any]] = Field(None, description="Información del error si la consulta falló.")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales.")

    model_config = {"extra": "forbid"}
