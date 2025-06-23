"""
Domain Actions para Agent Management Service.
INTEGRADO: Con sistema de Domain Actions existente.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
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
    agent_id: str = Field(..., description="ID del agente")
    # tenant_id for this action is typically expected at the root of DomainAction
    # or handled by context if it's a system-wide invalidation.
    
    def get_domain(self) -> str:
        return "management"
    
    def get_action_name(self) -> str:
        return "invalidate_cache"

class GetAgentConfigData(BaseModel):
    """Data payload for GetAgentConfigAction."""
    agent_id: str = Field(..., description="ID del agente a obtener")
    tenant_id: str = Field(..., description="ID del tenant propietario del agente")

class GetAgentConfigAction(DomainAction):
    """Domain Action para obtener la configuración de un agente."""
    action_type: str = Field("management.get_agent_config", const=True, default="management.get_agent_config")
    data: GetAgentConfigData

    class Config:
        schema_extra = {
            "example": {
                "action_id": "unique-action-id-123",
                "action_type": "management.get_agent_config",
                "timestamp": "2024-05-20T10:00:00Z",
                "origin_service": "agent_execution_service",
                "tenant_id": "tenant-abc", # Root tenant_id
                "session_id": "session-xyz", # Optional root session_id
                "correlation_id": "corr-id-456", # Optional root correlation_id
                "data": {
                    "agent_id": "agent-def-789",
                    "tenant_id": "tenant-abc" # tenant_id specific to data payload
                }
            }
        }

    def get_domain(self) -> str:
        return "management"

    def get_action_name(self) -> str:
        return "get_agent_config"


class UpdateAgentConfigData(BaseModel):
    """Data payload for UpdateAgentConfigAction."""
    agent_id: str = Field(..., description="ID del agente a actualizar")
    tenant_id: str = Field(..., description="ID del tenant propietario del agente")
    update_data: Dict[str, Any] = Field(..., description="Datos a actualizar en la configuración del agente")

class UpdateAgentConfigAction(DomainAction):
    """Domain Action para actualizar la configuración de un agente."""
    action_type: str = Field("management.update_agent_config", const=True, default="management.update_agent_config")
    data: UpdateAgentConfigData

    def get_domain(self) -> str:
        return "management"

    def get_action_name(self) -> str:
        return "update_agent_config"

class DeleteAgentConfigData(BaseModel):
    """Data payload for DeleteAgentConfigAction."""
    agent_id: str = Field(..., description="ID del agente a eliminar")
    tenant_id: str = Field(..., description="ID del tenant propietario del agente")

class DeleteAgentConfigAction(DomainAction):
    """Domain Action para eliminar la configuración de un agente."""
    action_type: Literal["management.delete_agent_config"] = "management.delete_agent_config"
    data: DeleteAgentConfigData

    def get_domain(self) -> str:
        return "management"

    def get_action_name(self) -> str:
        return "delete_agent_config"

# Action for Ingestion Service to notify AMS about collection status
class CollectionIngestionStatusData(BaseModel):
    collection_id: str
    tenant_id: str
    status: str # e.g., 'COMPLETED', 'FAILED'
    message: Optional[str] = None

class CollectionIngestionStatusAction(DomainAction):
    action_type: Literal["management.collection_ingestion_status"] = "management.collection_ingestion_status"
    data: CollectionIngestionStatusData

    def get_domain(self) -> str:
        return "management"

    def get_action_name(self) -> str:
        return "collection_ingestion_status"