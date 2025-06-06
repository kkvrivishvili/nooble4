"""
Modelos para ejecución de agentes.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum

class ExecutionStatus(str, Enum):
    """Estados de ejecución."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class ExecutionRequest(BaseModel):
    """Request para ejecutar un agente."""
    
    task_id: str = Field(..., description="ID único de la tarea")
    tenant_id: str = Field(..., description="ID del tenant")
    agent_id: UUID = Field(..., description="ID del agente")
    session_id: str = Field(..., description="ID de la sesión")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversación")
    
    # Mensaje del usuario
    message: str = Field(..., description="Mensaje del usuario")
    message_type: str = Field("text", description="Tipo de mensaje")
    
    # Información del usuario
    user_info: Dict[str, Any] = Field(default_factory=dict, description="Info del usuario")
    
    # Contexto adicional
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos")
    
    # Configuración de ejecución
    max_iterations: Optional[int] = Field(None, description="Máximo de iteraciones")
    timeout: Optional[int] = Field(None, description="Timeout personalizado")
    
    # Callback para respuesta
    callback_queue: Optional[str] = Field(None, description="Cola de callback")

class ExecutionResult(BaseModel):
    """Resultado de ejecución de agente."""
    
    task_id: str = Field(..., description="ID de la tarea")
    status: ExecutionStatus = Field(..., description="Estado de la ejecución")
    
    # Resultado principal
    response: Optional[str] = Field(None, description="Respuesta del agente")
    
    # Información de herramientas y fuentes
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Herramientas usadas")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Fuentes consultadas")
    
    # Metadatos de ejecución
    execution_time: Optional[float] = Field(None, description="Tiempo de ejecución")
    iterations_used: Optional[int] = Field(None, description="Iteraciones utilizadas")
    tokens_used: Optional[int] = Field(None, description="Tokens utilizados")
    
    # Error info (si aplica)
    error: Optional[Dict[str, Any]] = Field(None, description="Información de error")
    
    # Información del agente
    agent_info: Dict[str, Any] = Field(default_factory=dict, description="Info del agente usado")
    
    # Timestamps
    started_at: Optional[datetime] = Field(None, description="Inicio de ejecución")
    completed_at: Optional[datetime] = Field(None, description="Fin de ejecución")
