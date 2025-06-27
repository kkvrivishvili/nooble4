"""
Modelos para gestión de sesiones y estado en Agent Orchestrator.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class SessionState(BaseModel):
    """Estado de una sesión de chat activa."""
    
    session_id: str = Field(..., description="ID único de la sesión")
    tenant_id: str = Field(..., description="ID del tenant")
    agent_id: str = Field(..., description="ID del agente en uso")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    
    # Estado de conexión
    connection_id: Optional[str] = Field(None, description="ID de conexión WebSocket actual")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    # Tracking de conversación
    conversation_id: Optional[str] = Field(None, description="ID de conversación en Execution Service")
    current_task_id: Optional[str] = Field(None, description="Task ID actual en proceso")
    task_count: int = Field(default=0, description="Número de tareas procesadas")
    
    # Métricas
    messages_sent: int = Field(default=0)
    messages_received: int = Field(default=0)
    errors_count: int = Field(default=0)
    
    # Metadata adicional
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "tenant-123",
                "agent_id": "agent-456",
                "user_id": "user-789",
                "connection_id": "conn-abc",
                "conversation_id": "conv-xyz",
                "current_task_id": "task-123",
                "task_count": 5,
                "messages_sent": 10,
                "messages_received": 10
            }
        }


class ConnectionInfo(BaseModel):
    """Información de una conexión WebSocket."""
    
    connection_id: str = Field(..., description="ID único de la conexión")
    session_id: str = Field(..., description="ID de la sesión")
    tenant_id: str = Field(..., description="ID del tenant")
    agent_id: str = Field(..., description="ID del agente")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_ping: Optional[datetime] = Field(None)
    
    # Información del cliente
    user_agent: Optional[str] = Field(None)
    ip_address: Optional[str] = Field(None)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatTask(BaseModel):
    """Representa una tarea de chat individual."""
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="ID de la sesión")
    
    # Mensaje
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field(default="text", description="Tipo de mensaje")
    
    # Estado
    status: str = Field(default="pending", description="Estado de la tarea")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)
    
    # Respuesta
    response: Optional[str] = Field(None, description="Respuesta del agente")
    error: Optional[str] = Field(None, description="Error si falló")
    
    # Métricas
    execution_time_ms: Optional[int] = Field(None)
    tokens_used: Optional[Dict[str, int]] = Field(None)


class ConversationContext(BaseModel):
    """Contexto de una conversación para mantener estado."""
    
    conversation_id: str = Field(..., description="ID de la conversación")
    session_id: str = Field(..., description="ID de la sesión")
    tenant_id: str = Field(..., description="ID del tenant")
    agent_id: str = Field(..., description="ID del agente")
    
    # Historial reciente (últimos N mensajes)
    recent_messages: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Últimos mensajes para contexto"
    )
    
    # Estado de la conversación
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = Field(default=0)
    
    # Configuraciones activas
    mode: str = Field(default="simple", description="Modo de chat (simple/advance)")
    
    def add_message(self, role: str, content: str):
        """Agrega un mensaje al historial reciente."""
        self.recent_messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Mantener solo los últimos 10 mensajes
        if len(self.recent_messages) > 10:
            self.recent_messages = self.recent_messages[-10:]
        
        self.message_count += 1
        self.updated_at = datetime.utcnow()