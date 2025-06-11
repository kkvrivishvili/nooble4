"""
Modelos de datos para el servicio de conversaciones.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from enum import Enum

class ConversationStatus(str, Enum):
    """Estados de una conversación."""
    ACTIVE = "active"
    COMPLETED = "completed"
    TRANSFERRED = "transferred"  # Movida a PostgreSQL
    ARCHIVED = "archived"

class MessageRole(str, Enum):
    """Roles en una conversación."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"

class Message(BaseModel):
    """Modelo optimizado de mensaje."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    role: MessageRole
    content: str
    
    # Metadatos esenciales
    tokens_estimate: Optional[int] = None  # Estimación de tokens para el mensaje
    processing_time_ms: Optional[int] = None
    agent_id: Optional[str] = None
    model_used: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata para estadísticas
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Conversation(BaseModel):
    """Modelo optimizado de conversación."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    session_id: str
    agent_id: str  # Simplificado: un agente principal
    user_id: Optional[str] = None
    
    # Estado y configuración
    status: ConversationStatus = ConversationStatus.ACTIVE
    model_name: str = "llama3-8b-8192"  # Modelo de IA utilizado en la conversación
    
    # Métricas en tiempo real
    message_count: int = 0
    total_tokens: int = 0
    
    # Timestamps críticos
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None
    websocket_closed_at: Optional[datetime] = None
    
    # Metadatos para migración
    needs_migration: bool = False
    migrated_to_db: bool = False

class ConversationContext(BaseModel):
    """Contexto optimizado para Query Service."""
    
    conversation_id: str
    messages: List[Dict[str, Any]]  # Lista de mensajes en formato de diccionario
    total_tokens: int
    model_name: str
    truncation_applied: bool = False
    
class ConversationStats(BaseModel):
    """Estadísticas básicas de conversación."""
    
    tenant_id: str
    agent_id: str
    total_conversations: int = 0
    active_conversations: int = 0
    total_messages: int = 0
    avg_conversation_length: float = 0.0
    avg_response_time: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)
