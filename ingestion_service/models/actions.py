"""
Domain Actions para el servicio de ingestión de documentos.

Define las acciones específicas para el proceso de ingestión, chunking y generación de embeddings.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import Field, validator

from common.models.actions import DomainAction


class DocumentProcessAction(DomainAction):
    """Acción para procesar un documento completo."""
    
    # Identificadores
    document_id: str
    collection_id: str
    tenant_id: str
    session_id: Optional[str] = None
    
    # Fuentes (solo una debe estar presente)
    file_key: Optional[str] = None  # Para documentos en storage
    url: Optional[str] = None  # Para ingestión desde URL
    text_content: Optional[str] = None  # Para texto plano
    
    # Metadatos
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Configuración del procesamiento
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    embedding_model: Optional[str] = None
    
    # Configuración del sistema
    callback_queue: Optional[str] = None
    task_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "document"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "process"
    
    @validator("file_key", "url", "text_content")
    def validate_source(cls, v, values):
        """Valida que al menos una fuente esté presente."""
        if not v and not values.get("file_key") and not values.get("url") and not values.get("text_content"):
            raise ValueError("Al menos un origen de documento (file_key, url o text_content) debe estar presente")
        return v


class DocumentChunkAction(DomainAction):
    """Acción para fragmentar un documento en chunks."""
    
    document_id: str
    collection_id: str
    tenant_id: str
    session_id: Optional[str] = None
    text_content: str
    
    # Metadatos
    title: Optional[str] = None
    document_metadata: Optional[Dict[str, Any]] = None
    
    # Configuración
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    chunking_strategy: Optional[str] = "sentence"  # sentence, paragraph, fixed
    
    # Configuración del sistema
    task_id: str
    callback_queue: Optional[str] = None
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "document"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "chunk"


class EmbeddingRequestAction(DomainAction):
    """Acción para solicitar embeddings al servicio de embedding."""
    
    document_id: str
    collection_id: str
    tenant_id: str
    session_id: Optional[str] = None
    chunks: List[Dict[str, Any]]  # Lista de chunks con texto y metadatos
    
    # Configuración
    model: Optional[str] = None
    
    # Configuración del sistema
    task_id: str
    callback_queue: str
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "embedding"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "generate"


class EmbeddingCallbackAction(DomainAction):
    """Acción recibida como callback del servicio de embeddings."""
    
    document_id: str
    collection_id: str
    tenant_id: str
    task_id: str
    
    # Resultados
    status: str  # "success" o "error"
    embeddings: Optional[List[List[float]]] = None
    error: Optional[str] = None
    
    # Metadatos
    chunks: Optional[List[Dict[str, Any]]] = None
    model: Optional[str] = None
    dimensions: Optional[int] = None
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "embedding"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "callback"


class TaskStatusAction(DomainAction):
    """Acción para consultar el estado de una tarea."""
    
    task_id: str
    tenant_id: str
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "task"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "status"


class TaskCancelAction(DomainAction):
    """Acción para cancelar una tarea en proceso."""
    
    task_id: str
    tenant_id: str
    
    @validator("domain", pre=True, always=True)
    def set_domain(cls, v):
        return "task"
    
    @validator("action", pre=True, always=True)
    def set_action(cls, v):
        return "cancel"
