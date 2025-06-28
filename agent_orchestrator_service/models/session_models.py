"""
Modelos para gestión de sesiones en Agent Orchestrator.
Simplificados para no duplicar funcionalidad con otros servicios.
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from common.models.config_models import ExecutionConfig, QueryConfig, RAGConfig


class SessionState(BaseModel):
    """Estado interno de una sesión en el Orchestrator."""
    
    # IDs principales
    session_id: uuid.UUID = Field(..., description="ID único de la sesión generado por orchestrator")
    tenant_id: uuid.UUID = Field(..., description="ID del tenant desde JWT")
    agent_id: uuid.UUID = Field(..., description="ID del agente desde JWT")
    user_id: Optional[uuid.UUID] = Field(None, description="ID del usuario desde JWT")
    
    # Estado de conexión WebSocket
    connection_id: Optional[str] = Field(None, description="ID de conexión WebSocket actual")
    websocket_connected: bool = Field(default=False, description="Si hay WebSocket activo")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    # Cache de configuración del agente
    agent_config: Optional[Dict[str, Any]] = Field(None, description="Configuraciones cacheadas")
    config_fetched_at: Optional[datetime] = Field(None, description="Cuándo se obtuvo la config")
    
    # Tracking
    total_tasks: int = Field(default=0, description="Total de task_ids generados")
    active_task_id: Optional[uuid.UUID] = Field(None, description="Task actual en proceso")
    
    class Config:
        arbitrary_types_allowed = True


class ChatInitRequest(BaseModel):
    """Request para iniciar una sesión de chat."""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatInitResponse(BaseModel):
    """Response al iniciar una sesión de chat."""
    session_id: uuid.UUID
    task_id: uuid.UUID
    websocket_url: str
    status: str = "ready"


class ChatMessageRequest(BaseModel):
    """Request de mensaje de chat vía WebSocket."""
    message: str = Field(..., description="Mensaje del usuario")
    type: str = Field(default="text", description="Tipo de mensaje")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)