"""
Modelos Pydantic para respuestas del Agent Execution Service.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SimpleExecutionResponse(BaseModel):
    """Respuesta para execution.chat.simple."""
    message: str = Field(..., description="Respuesta del agente")
    sources: List[str] = Field(default_factory=list, description="IDs de documentos usados")
    conversation_id: str = Field(..., description="ID de la conversación")
    execution_time_ms: int = Field(..., description="Tiempo de ejecución en ms")


class AdvanceExecutionResponse(BaseModel):
    """Respuesta para execution.chat.advance."""
    message: str = Field(..., description="Respuesta final del agente")
    thinking: List[str] = Field(default_factory=list, description="Pensamientos del agente")
    tools_used: List[str] = Field(default_factory=list, description="Herramientas utilizadas")
    conversation_id: str = Field(..., description="ID de la conversación")
    execution_time_ms: int = Field(..., description="Tiempo de ejecución en ms")
    iterations: int = Field(..., description="Número de iteraciones ReAct")