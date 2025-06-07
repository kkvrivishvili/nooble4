"""
Modelos de Domain Actions para Query Service.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import Field, validator

from common.models.actions import DomainAction

class QueryGenerateAction(DomainAction):
    """
    Domain Action para procesar consultas RAG con embeddings pre-calculados.
    """
    action_type: str = "query.generate"
    
    # Campos de identificación
    task_id: str = Field(..., description="ID único de la tarea")
    tenant_id: str = Field(..., description="ID del tenant")
    session_id: str = Field(..., description="ID de la sesión")
    callback_queue: str = Field(..., description="Cola para callback")
    
    # Datos de la consulta
    query: str = Field(..., description="Texto de la consulta")
    query_embedding: List[float] = Field(..., description="Embedding pre-calculado del query")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Metadatos opcionales
    agent_id: Optional[str] = Field(None, description="ID del agente")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversación")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")
    
    # Configuración de la consulta
    similarity_top_k: int = Field(4, description="Número de documentos similares")
    response_mode: str = Field("compact", description="Modo de respuesta")
    llm_model: Optional[str] = Field(None, description="Modelo LLM específico")
    include_sources: bool = Field(True, description="Incluir fuentes en la respuesta")
    max_sources: int = Field(3, description="Máximo de fuentes a incluir")
    
    # Campos para manejo de fallback
    agent_description: Optional[str] = Field(None, description="Descripción del agente para fallback")
    fallback_behavior: str = Field("agent_knowledge", description="Comportamiento de fallback")
    relevance_threshold: float = Field(0.75, description="Umbral para documentos relevantes")

    @validator("query")
    def validate_query(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("La consulta no puede estar vacía")
        return v

class SearchDocsAction(DomainAction):
    """
    Domain Action para búsqueda de documentos sin generación de respuesta.
    """
    action_type: str = "query.search"
    
    # Campos de identificación
    task_id: str = Field(..., description="ID único de la tarea")
    tenant_id: str = Field(..., description="ID del tenant")
    session_id: str = Field(..., description="ID de la sesión")
    callback_queue: str = Field(..., description="Cola para callback")
    
    # Datos de la búsqueda
    query_embedding: List[float] = Field(..., description="Embedding para búsqueda")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Configuración de búsqueda
    limit: int = Field(5, description="Número máximo de resultados")
    similarity_threshold: float = Field(0.7, description="Umbral de similitud")
    metadata_filter: Optional[Dict[str, Any]] = Field(None, description="Filtro por metadatos")
    
    # Metadatos opcionales
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")

class QueryCallbackAction(DomainAction):
    """
    Domain Action para callbacks de consultas.
    """
    action_type: str = "query.callback"
    
    # Campos de identificación
    task_id: str = Field(..., description="ID de la tarea original")
    tenant_id: str = Field(..., description="ID del tenant")
    status: str = Field("completed", description="Estado: completed o error")
    
    # Resultado de la consulta
    result: Dict[str, Any] = Field(..., description="Resultado de la consulta")
    
    # Datos de error (si aplica)
    error: Optional[Dict[str, Any]] = Field(None, description="Datos del error si status=error")
