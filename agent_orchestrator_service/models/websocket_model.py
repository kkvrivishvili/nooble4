"""
Modelos para la comunicación WebSocket en Agent Orchestrator Service.

Define las estructuras de mensajes y tipos utilizados en la comunicación
en tiempo real a través de WebSockets.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field


class WebSocketMessageType(str, Enum):
    """Tipos de mensajes WebSocket soportados."""
    # Tipos básicos
    CONNECTION_ACK = "connection_ack"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    
    # Estados de tareas
    TASK_START = "task_start"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    
    # Flujo de chat
    USER_MESSAGE = "user_message"
    AGENT_RESPONSE = "agent_response"
    AGENT_THINKING = "agent_thinking"
    
    # Llamadas a herramientas
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # Control de sesión
    SESSION_UPDATE = "session_update"
    SESSION_END = "session_end"
    
    # Streaming
    STREAM_START = "stream_start"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"


class WebSocketMessage(BaseModel):
    """
    Modelo base para todos los mensajes WebSocket.
    
    Atributos:
        type: Tipo de mensaje (ver WebSocketMessageType)
        data: Contenido principal del mensaje
        timestamp: Marca de tiempo del mensaje
        message_id: Identificador único del mensaje
        session_id: ID de la sesión asociada
        metadata: Metadatos adicionales
    """
    type: WebSocketMessageType = Field(..., description="Tipo de mensaje WebSocket")
    data: Dict[str, Any] = Field(default_factory=dict, description="Datos del mensaje")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Marca de tiempo del mensaje")
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="ID único del mensaje")
    session_id: Optional[str] = Field(None, description="ID de la sesión asociada")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "type": "agent_response",
                "data": {"content": "Hola, ¿en qué puedo ayudarte hoy?"},
                "timestamp": "2023-01-01T12:00:00Z",
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "session_id": "session-123",
                "metadata": {"source": "agent", "model": "llama3-70b"}
            }
        }


class ConnectionStatus(str, Enum):
    """Estados posibles de una conexión WebSocket."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ConnectionInfo(BaseModel):
    """Información detallada sobre una conexión WebSocket."""
    connection_id: str = Field(..., description="ID único de la conexión")
    session_id: str = Field(..., description="ID de la sesión asociada")
    status: ConnectionStatus = Field(default=ConnectionStatus.CONNECTING, description="Estado actual de la conexión")
    connected_at: datetime = Field(default_factory=datetime.utcnow, description="Momento de conexión")
    last_activity: Optional[datetime] = Field(None, description="Última actividad registrada")
    user_agent: Optional[str] = Field(None, description="User-Agent del cliente")
    ip_address: Optional[str] = Field(None, description="Dirección IP del cliente")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        use_enum_values = True