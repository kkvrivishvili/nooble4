"""
Modelos para mensajes WebSocket.
Simplificados para usar con el flujo estándar.
"""
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class WebSocketMessageType(str, Enum):
    """Tipos de mensajes WebSocket."""
    # Control
    CONNECTION_ACK = "connection_ack"
    ERROR = "error"
    
    # Chat
    TASK_CREATED = "task_created"
    RESPONSE = "response"
    STREAM_CHUNK = "stream_chunk"
    TASK_COMPLETED = "task_completed"


class WebSocketMessage(BaseModel):
    """Mensaje WebSocket estándar."""
    type: WebSocketMessageType
    task_id: Optional[uuid.UUID] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }