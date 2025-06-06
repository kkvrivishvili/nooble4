"""
Domain Actions específicas para Agent Orchestrator Service.

Define las acciones para comunicación entre servicios
relativas a la orquestación de agentes y gestión de WebSockets.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import Field

from common.models.actions import DomainAction

class WebSocketSendAction(DomainAction):
    """Domain Action para enviar mensajes via WebSocket."""
    
    action_type: str = Field("websocket.send", description="Tipo de acción")
    
    # Datos específicos
    session_id: str = Field(..., description="ID de la sesión")
    message_data: Dict[str, Any] = Field(..., description="Datos del mensaje")
    message_type: str = Field("agent_response", description="Tipo de mensaje WS")
    
    def get_domain(self) -> str:
        return "websocket"
    
    def get_action_name(self) -> str:
        return "send"

class WebSocketBroadcastAction(DomainAction):
    """Domain Action para broadcast a todas las conexiones de un tenant."""
    
    action_type: str = Field("websocket.broadcast", description="Tipo de acción")
    
    # Datos específicos
    message_data: Dict[str, Any] = Field(..., description="Datos del mensaje")
    message_type: str = Field("broadcast", description="Tipo de mensaje WS")
    target_sessions: Optional[List[str]] = Field(None, description="Sesiones específicas")
    
    def get_domain(self) -> str:
        return "websocket"
    
    def get_action_name(self) -> str:
        return "broadcast"

class ChatProcessAction(DomainAction):
    """Domain Action para procesar mensajes de chat."""
    
    action_type: str = Field("chat.process", description="Tipo de acción")
    
    # Datos de agente y chat
    agent_id: UUID = Field(..., description="ID del agente a usar")
    message: str = Field(..., description="Mensaje del usuario")
    session_id: str = Field(..., description="ID de la sesión")
    conversation_id: Optional[UUID] = Field(None, description="ID de conversación")
    
    # Información adicional
    message_type: str = Field("text", description="Tipo de mensaje")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    
    # Control
    timeout: Optional[int] = Field(None, description="Timeout personalizado")
    callback_queue: str = Field(..., description="Cola para callbacks")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "process"

class ChatStatusAction(DomainAction):
    """Domain Action para consultar estado de tarea."""
    
    action_type: str = Field("chat.status", description="Tipo de acción")
    
    # Datos específicos
    task_id: str = Field(..., description="ID de la tarea")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "status"

class ChatCancelAction(DomainAction):
    """Domain Action para cancelar tarea."""
    
    action_type: str = Field("chat.cancel", description="Tipo de acción")
    
    # Datos específicos
    task_id: str = Field(..., description="ID de la tarea")
    reason: Optional[str] = Field(None, description="Motivo de cancelación")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "cancel"
