"""
Domain Actions específicas para Agent Orchestrator Service.

MODIFICADO: Integración con ExecutionContext y sistema de colas por tier.
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import Field, validator
from datetime import datetime

from common.models.actions import DomainAction

class ChatSendMessageAction(DomainAction):
    """Domain Action para enviar mensaje de chat."""
    
    action_type: str = Field("chat.send", description="Tipo de acción")
    
    # Datos del mensaje
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    
    # MODIFICADO: Execution context ya viene en DomainAction base
    # Ya no necesitamos campos específicos aquí
    
    # NUEVO: Metadatos específicos del chat
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "send"


class ChatProcessAction(DomainAction):
    """Domain Action para procesar mensajes de chat en Agent Execution."""
    
    action_type: str = Field("execution.agent_run", description="Tipo de acción")
    
    # Datos específicos del procesamiento
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    
    # NUEVO: Configuración de ejecución específica
    max_iterations: Optional[int] = Field(None, description="Máximo iteraciones del agente")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "agent_run"


class ExecutionCallbackAction(DomainAction):
    """Domain Action para callbacks de ejecución completada."""
    
    action_type: str = Field("execution.callback", description="Tipo de acción")
    
    # Estado de la ejecución
    status: str = Field(..., description="Estado: completed, failed, timeout")
    
    # Resultado de la ejecución
    result: Dict[str, Any] = Field(..., description="Resultado de la ejecución")
    
    # NUEVO: Métricas de performance
    execution_time: Optional[float] = Field(None, description="Tiempo total de ejecución")
    tokens_used: Optional[Dict[str, int]] = Field(None, description="Tokens utilizados")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "callback"


class WebSocketSendAction(DomainAction):
    """Domain Action para enviar mensajes via WebSocket."""
    
    action_type: str = Field("websocket.send", description="Tipo de acción")
    
    # Datos específicos del WebSocket
    message_data: Dict[str, Any] = Field(..., description="Datos del mensaje")
    message_type: str = Field("agent_response", description="Tipo de mensaje WS")
    
    def get_domain(self) -> str:
        return "websocket"
    
    def get_action_name(self) -> str:
        return "send"


class WebSocketBroadcastAction(DomainAction):
    """Domain Action para broadcast a múltiples conexiones."""
    
    action_type: str = Field("websocket.broadcast", description="Tipo de acción")
    
    # Datos específicos del broadcast
    message_data: Dict[str, Any] = Field(..., description="Datos del mensaje")
    message_type: str = Field("broadcast", description="Tipo de mensaje WS")
    target_sessions: Optional[List[str]] = Field(None, description="Sesiones específicas")
    
    def get_domain(self) -> str:
        return "websocket"
    
    def get_action_name(self) -> str:
        return "broadcast"


class ChatStatusAction(DomainAction):
    """Domain Action para consultar estado de chat."""
    
    action_type: str = Field("chat.status", description="Tipo de acción")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "status"


class ChatCancelAction(DomainAction):
    """Domain Action para cancelar procesamiento de chat."""
    
    action_type: str = Field("chat.cancel", description="Tipo de acción")
    
    reason: Optional[str] = Field(None, description="Razón de cancelación")
    
    def get_domain(self) -> str:
        return "chat"
    
    def get_action_name(self) -> str:
        return "cancel"