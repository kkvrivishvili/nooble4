"""
Modelos de Domain Actions para Query Service.
MODIFICADO: Integración con ExecutionContext y sistema de colas por tier.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import Field, validator

from common.models.actions import DomainAction

class QueryGenerateAction(DomainAction):
    """
    Domain Action para procesar consultas RAG con embeddings pre-calculados.
    MODIFICADO: Usar ExecutionContext del DomainAction base.
    """
    action_type: str = "query.generate"
    
    # MODIFICADO: Ya no necesitamos campos específicos de contexto
    # porque execution_context viene en DomainAction base
    
    # Datos de la consulta
    query: str = Field(..., description="Texto de la consulta")
    query_embedding: List[float] = Field(..., description="Embedding pre-calculado del query")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Metadatos opcionales
    agent_id: Optional[str] = Field(None, description="ID del agente")
    conversation_id: Optional[UUID] = Field(None, description="ID de la conversación")
    
    # Configuración de la consulta
    similarity_top_k: int = Field(4, description="Número de documentos similares")
    llm_model: Optional[str] = Field(None, description="Modelo LLM específico")
    include_sources: bool = Field(True, description="Incluir fuentes en la respuesta")
    max_sources: int = Field(3, description="Máximo de fuentes a incluir")
    
    # Campos para manejo de fallback
    agent_description: Optional[str] = Field(None, description="Descripción del agente para fallback")
    fallback_behavior: str = Field("use_agent_knowledge", description="Comportamiento de fallback")
    relevance_threshold: float = Field(0.75, description="Umbral para documentos relevantes")

    @validator("query")
    def validate_query(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("La consulta no puede estar vacía")
        return v
    
    def get_domain(self) -> str:
        return "query"
    
    def get_action_name(self) -> str:
        return "generate"

class SearchDocsAction(DomainAction):
    """
    Domain Action para búsqueda de documentos sin generación de respuesta.
    MODIFICADO: Usar ExecutionContext del DomainAction base.
    """
    action_type: str = "query.search"
    
    # MODIFICADO: Ya no necesitamos campos específicos de contexto
    
    # Datos de la búsqueda
    query_embedding: List[float] = Field(..., description="Embedding para búsqueda")
    collection_id: str = Field(..., description="ID de la colección")
    
    # Configuración de búsqueda
    limit: int = Field(5, description="Número máximo de resultados")
    similarity_threshold: float = Field(0.7, description="Umbral de similitud")
    metadata_filter: Optional[Dict[str, Any]] = Field(None, description="Filtro por metadatos")
    
    def get_domain(self) -> str:
        return "query"
    
    def get_action_name(self) -> str:
        return "search"

class QueryCallbackAction(DomainAction):
    """
    Domain Action para callbacks de consultas.
    MODIFICADO: Integración con sistema de callbacks por tier.
    """
    action_type: str = "query.callback"
    
    # Estado de la consulta
    status: str = Field("completed", description="Estado: completed, failed")
    
    # Resultado de la consulta
    result: Dict[str, Any] = Field(..., description="Resultado de la consulta")
    
    # NUEVO: Métricas de performance
    processing_time: Optional[float] = Field(None, description="Tiempo de procesamiento")
    tokens_used: Optional[int] = Field(None, description="Tokens utilizados en LLM")
    
    # Datos de error (si aplica)
    error: Optional[Dict[str, Any]] = Field(None, description="Datos del error si status=failed")
    
    def get_domain(self) -> str:
        return "query"
    
    def get_action_name(self) -> str:
        return "callback"

# NUEVO: Domain Actions para interacción con Embedding Service
class EmbeddingRequestAction(DomainAction):
    """Domain Action para solicitar embeddings al Embedding Service."""
    
    action_type: str = Field("embedding.request", description="Tipo de acción")
    
    texts: List[str] = Field(..., description="Textos para generar embeddings")
    model: Optional[str] = Field(None, description="Modelo de embedding")
    
    def get_domain(self) -> str:
        return "embedding"
    
    def get_action_name(self) -> str:
        return "request"