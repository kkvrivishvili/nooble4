"""
Domain Actions para Conversation Service.
"""

from typing import Dict, Any, Optional
from pydantic import Field
from common.models.actions import DomainAction

class SaveMessageAction(DomainAction):
    """Domain Action para guardar mensaje."""
    
    action_type: str = Field("conversation.save_message", description="Tipo de acción")
    
    # Datos del mensaje
    role: str = Field(..., description="Rol del mensaje (user/assistant/system)")
    content: str = Field(..., description="Contenido del mensaje")
    agent_id: str = Field(..., description="ID del agente")
    model_name: str = Field("llama3-8b-8192", description="Modelo utilizado")
    user_id: Optional[str] = Field(None, description="ID del usuario")
    tokens_estimate: Optional[int] = Field(None, description="Estimación de tokens")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "save_message"

class GetContextAction(DomainAction):
    """Domain Action para obtener contexto."""
    
    action_type: str = Field("conversation.get_context", description="Tipo de acción")
    
    # Parámetros de contexto
    model_name: str = Field("llama3-8b-8192", description="Modelo para optimizar contexto")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "get_context"

class SessionClosedAction(DomainAction):
    """Domain Action para notificar cierre de sesión."""
    
    action_type: str = Field("conversation.session_closed", description="Tipo de acción")
    
    def get_domain(self) -> str:
        return "conversation"
    
    def get_action_name(self) -> str:
        return "session_closed"
