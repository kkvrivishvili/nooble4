"""
Modelos para la gestión de tareas de procesamiento en el servicio de ingestión.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

from common.models.base import BaseResponse


class TaskStatus(str, Enum):
    """Estados posibles de una tarea."""
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Tipos de tareas soportados."""
    DOCUMENT_PROCESSING = "document_processing"
    URL_PROCESSING = "url_processing"
    TEXT_PROCESSING = "text_processing"
    BATCH_PROCESSING = "batch_processing"


class TaskSource(str, Enum):
    """Origen de los datos para la tarea."""
    FILE = "file"
    URL = "url"
    TEXT = "text"
    BATCH = "batch"


class TaskProgress(BaseModel):
    """Modelo para el progreso de una tarea."""
    percentage: int = 0
    current_step: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Task(BaseModel):
    """Modelo principal para tareas de procesamiento."""
    task_id: str
    tenant_id: str
    status: TaskStatus
    type: TaskType
    source: TaskSource
    
    # Identificadores relacionados
    document_id: Optional[str] = None
    collection_id: Optional[str] = None
    
    # Metadatos
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Estadísticas y progreso
    progress: TaskProgress
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Información de error si aplica
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Resultados
    result: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True


class TaskCreateRequest(BaseModel):
    """Modelo para la creación de una tarea desde la API."""
    document_id: str
    collection_id: str
    tenant_id: str
    type: TaskType
    source: TaskSource
    
    # Depende del tipo de fuente
    file_key: Optional[str] = None
    url: Optional[str] = None
    text_content: Optional[str] = None
    
    # Metadatos opcionales
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskResponse(BaseResponse):
    """Respuesta estándar para operaciones con tareas."""
    task: Task


class TaskListResponse(BaseResponse):
    """Respuesta para listado de tareas con paginación."""
    tasks: List[Task]
    total: int
    page: int
    page_size: int
