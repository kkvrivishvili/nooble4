"""
Modelos para templates de agentes.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class TemplateCategory(str, Enum):
    """Categorías de templates."""
    SYSTEM = "system"
    CUSTOM = "custom"

class AgentTemplate(BaseModel):
    """Modelo de template de agente."""
    
    id: str
    name: str
    description: str
    category: TemplateCategory
    tenant_id: Optional[str] = None  # null para system templates
    
    # Configuración por defecto
    default_config: Dict[str, Any]
    
    # Requerimientos
    minimum_tier: str = "free"
    required_tools: List[str] = Field(default_factory=list)
    required_collections_count: Optional[int] = None
    
    # Metadata
    use_cases: List[str] = Field(default_factory=list)
    preview_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Gestión
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CreateTemplateRequest(BaseModel):
    """Request para crear template custom."""
    name: str
    description: str
    default_config: Dict[str, Any]
    required_tools: List[str] = Field(default_factory=list)
    required_collections_count: Optional[int] = None
    use_cases: List[str] = Field(default_factory=list)
    preview_config: Dict[str, Any] = Field(default_factory=dict)

class TemplateResponse(BaseModel):
    """Response con template."""
    success: bool = True
    message: str = ""
    template: AgentTemplate

class TemplateListResponse(BaseModel):
    """Response con lista de templates."""
    success: bool = True
    message: str = ""
    templates: List[AgentTemplate]
