"""
Modelos de datos para conversaciones.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum

class ConversationStatus(str, Enum):
    """Estados de una conversación."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    DELETED = "deleted"

class MessageRole(str, Enum):
    """Roles en una conversación."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"

class Message(BaseModel):
    """Modelo de mensaje individual."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    role: MessageRole
    content: str
    message_type: str = Field("text", description="Tipo de mensaje")
    
    # Metadatos
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None
    
    # Referencias
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    edited_at: Optional[datetime] = None

class Conversation(BaseModel):
    """Modelo de conversación completa."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    session_id: str
    
    # Participantes
    user_id: Optional[str] = None
    agent_ids: List[str] = Field(default_factory=list)
    primary_agent_id: str
    
    # Estado
    status: ConversationStatus = ConversationStatus.ACTIVE
    
    # Configuración
    context_window_size: int = 10
    retention_days: int = 90
    
    # Análisis
    sentiment_score: Optional[float] = None
    topics: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    language: str = "es"
    
    # CRM
    crm_contact_id: Optional[str] = None
    crm_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Métricas
    message_count: int = 0
    total_tokens: int = 0
    avg_response_time_ms: Optional[float] = None
    customer_satisfaction: Optional[float] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
