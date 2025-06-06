"""
Domain Actions para Agent Execution Service.

Define las acciones específicas para comunicación entre servicios
relacionadas con la ejecución de agentes.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import Field
from common.models.actions import DomainAction

class AgentExecutionAction(DomainAction):
    """Domain Action para solicitar ejecución de agente."""
    
    action_type: str = Field("execution.agent_run", description="Tipo de acción")
    
    # Datos específicos del agente
    agent_id: UUID = Field(..., description="ID del agente")
    session_id: str = Field(..., description="ID de la sesión")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversación")
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto")
    
    # Configuración
    timeout: Optional[int] = Field(None, description="Timeout personalizado")
    max_iterations: Optional[int] = Field(None, description="Máximo iteraciones")
    callback_queue: str = Field(..., description="Cola de callback para respuesta")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "agent_run"


class ExecutionCallbackAction(DomainAction):
    """Domain Action para enviar resultados de ejecución como callback."""
    
    action_type: str = Field("execution.callback", description="Tipo de acción")
    
    # Identificadores necesarios
    task_id: str = Field(..., description="ID de la tarea")
    session_id: str = Field(..., description="ID de la sesión")
    
    # Resultado de la ejecución
    status: str = Field("completed", description="Estado de la ejecución")
    result: Dict[str, Any] = Field(..., description="Resultado de la ejecución")
    
    # Métricas opcionales
    execution_time: Optional[float] = Field(None, description="Tiempo de ejecución en segundos")
    tokens_used: Optional[Dict[str, int]] = Field(None, description="Tokens utilizados")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "callback"
