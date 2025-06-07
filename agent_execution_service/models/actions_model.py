"""
Domain Actions para Agent Execution Service.

MODIFICADO: Integración con ExecutionContext y sistema de colas por tier.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import Field
from datetime import datetime

from common.models.actions import DomainAction

class AgentExecutionAction(DomainAction):
    """Domain Action para solicitar ejecución de agente."""
    
    action_type: str = Field("execution.agent_run", description="Tipo de acción")
    
    # MODIFICADO: Ya no necesitamos campos específicos de contexto
    # porque execution_context viene en DomainAction base
    
    # Datos específicos del mensaje
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
    """Domain Action para enviar resultados de ejecución como callback."""
    
    action_type: str = Field("execution.callback", description="Tipo de acción")
    
    # Estado de la ejecución
    status: str = Field("completed", description="Estado: completed, failed, timeout")
    
    # Resultado de la ejecución
    result: Dict[str, Any] = Field(..., description="Resultado de la ejecución")
    
    # NUEVO: Métricas de performance
    execution_time: Optional[float] = Field(None, description="Tiempo total de ejecución")
    tokens_used: Optional[Dict[str, int]] = Field(None, description="Tokens utilizados")
    
    def get_domain(self) -> str:
        return "execution"
    
    def get_action_name(self) -> str:
        return "callback"


# NUEVO: Domain Actions para interacción con otros servicios
class EmbeddingRequestAction(DomainAction):
    """Domain Action para solicitar embeddings."""
    
    action_type: str = Field("embedding.request", description="Tipo de acción")
    
    texts: list = Field(..., description="Textos para embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding")
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "request"


class QueryRequestAction(DomainAction):
    """Domain Action para solicitar consulta RAG."""
    
    action_type: str = Field("query.request", description="Tipo de acción")
    
    query: str = Field(..., description="Consulta a procesar")
    collection_id: str = Field(..., description="ID de colección")
    agent_description: Optional[str] = Field(None, description="Descripción del agente")
    
    def get_domain(self) -> str:
        return "query"
    
    def get_action_name(self) -> str:
        return "request"