"""
Execution Context - Modelo unificado para identificar contextos de ejecución.

Este módulo define el contexto de ejecución que puede ser:
- Un agente individual
- Un workflow multi-agente
- Una collection específica
- Otros tipos futuros
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ExecutionContext(BaseModel):
    """
    Contexto de ejecución unificado para agentes, workflows y collections.
    
    Attributes:
        context_id: Identificador único del contexto (ej: "agent-123", "workflow-456")
        context_type: Tipo de contexto ("agent", "workflow", "collection")
        tenant_id: ID del tenant propietario
        session_id: (Opcional) ID de la sesión de conversación o interacción.
        primary_agent_id: ID del agente principal/inicial
        agents: Lista de todos los agentes involucrados
        collections: Lista de todas las collections utilizadas
        metadata: Metadatos específicos del contexto
        created_at: Timestamp de creación
    """
    
    context_id: str
    context_type: str  # "agent", "workflow", "collection"
    tenant_id: str
    session_id: Optional[str] = None
    primary_agent_id: str
    agents: List[str]
    collections: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
