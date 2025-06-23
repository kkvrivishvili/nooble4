"""
Modelos de datos para agentes.
INTEGRADO: Con ExecutionContext para contextos de ejecución.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator
from enum import Enum

class AgentType(str, Enum):
    """Tipos de agentes."""
    CONVERSATIONAL = "conversational"
    RAG = "rag"
    WORKFLOW = "workflow"

class AgentStatus(str, Enum):
    """Estados de un agente."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

class Agent(BaseModel):
    """Modelo principal de agente."""
    
    # Identificación
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    description: Optional[str] = None
    slug: str  # Para URLs públicas usuario.nooble.ai/slug
    
    # Configuración Core
    type: AgentType = AgentType.CONVERSATIONAL
    model: str = "llama3-8b-8192"
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(2048, ge=1, le=8192)
    system_prompt: str
    
    # Herramientas y Capacidades
    tools: List[str] = Field(default_factory=list)
    collections: List[str] = Field(default_factory=list)
    
    # Configuración Avanzada
    max_iterations: int = Field(5, ge=1, le=20)
    max_history_messages: int = Field(10, ge=1, le=50)
    
    # Gestión
    is_active: bool = True
    is_public: bool = False  # Para usuario.nooble.ai/agente
    minimum_tier: str = "free"
    
    # Template Info
    template_id: Optional[str] = None
    created_from_template: bool = False
    
    # Metadatos
    tags: List[str] = Field(default_factory=list)
    usage_count: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    @validator('slug')
    def validate_slug(cls, v):
        """Valida que el slug sea URL-safe."""
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug debe contener solo letras minúsculas, números y guiones')
        return v
    
    def to_execution_context(self, tenant_tier: str) -> Dict[str, Any]:
        """Convierte agente a ExecutionContext."""
        from common.models.execution_context import create_agent_context
        
        context = create_agent_context(
            agent_id=self.id,
            tenant_id=self.tenant_id,
            tenant_tier=tenant_tier,
            collection_id=self.collections[0] if self.collections else "",
            metadata={
                "agent_name": self.name,
                "agent_type": self.type,
                "model": self.model,
                "tools": self.tools
            }
        )
        return context.to_dict()

class CreateAgentRequest(BaseModel):
    """Request para crear agente."""
    name: str
    description: Optional[str] = None
    slug: str
    type: AgentType = AgentType.CONVERSATIONAL
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: str
    tools: List[str] = Field(default_factory=list)
    collections: List[str] = Field(default_factory=list)
    max_iterations: Optional[int] = None
    max_history_messages: Optional[int] = None
    is_public: bool = False
    tags: List[str] = Field(default_factory=list)
    template_id: Optional[str] = None

class UpdateAgentRequest(BaseModel):
    """Request para actualizar agente."""
    name: Optional[str] = None
    description: Optional[str] = None
    slug: Optional[str] = None
    type: Optional[AgentType] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    collections: Optional[List[str]] = None
    max_iterations: Optional[int] = None
    max_history_messages: Optional[int] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None

class AgentResponse(BaseModel):
    """Response con agente."""
    success: bool = True
    message: str = ""
    agent: Agent

class AgentListResponse(BaseModel):
    """Response con lista de agentes."""
    success: bool = True
    message: str = ""
    agents: List[Agent]
    total: int
    page: int
    page_size: int

