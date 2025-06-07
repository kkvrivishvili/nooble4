"""
Domain Actions para Agent Management Service.
INTEGRADO: Con sistema de Domain Actions existente.
"""

from typing import Dict, Any, Optional, List
from pydantic import Field
from common.models.actions import DomainAction

class AgentValidationAction(DomainAction):
    """Domain Action para validar configuración de agente."""
    
    action_type: str = Field("management.validate_agent", description="Tipo de acción")
    
    # Datos del agente a validar
    agent_config: Dict[str, Any] = Field(..., description="Configuración del agente")
    collections: List[str] = Field(default_factory=list, description="Collections a validar")
    
    def get_domain(self) -> str:
        return "management"
    
    def get_action_name(self) -> str:
        return "validate_agent"

class CacheInvalidationAction(DomainAction):
    """Domain Action para invalidar cache de agente."""
    
    action_type: str = Field("management.invalidate_cache", description="Tipo de acción")
    
    # Datos para invalidación
    agent_id: str = Field(..., description="ID del agente")
    
    def get_domain(self) -> str:
        return "management"
    
    def get_action_name(self) -> str:
        return "invalidate_cache"