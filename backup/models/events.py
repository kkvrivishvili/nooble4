"""
Modelos para eventos en tiempo real transmitidos a través de WebSockets.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

from ingestion_service.models.tasks import TaskStatus


class EventType(str, Enum):
    """Tipos de eventos que se pueden transmitir vía WebSockets."""
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    PROGRESS_UPDATED = "progress_updated"
    DOCUMENT_RECEIVED = "document_received"
    TEXT_EXTRACTED = "text_extracted"
    CHUNKING_COMPLETED = "chunking_completed"
    EMBEDDING_STARTED = "embedding_started"
    EMBEDDING_COMPLETED = "embedding_completed"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


class WebSocketEvent(BaseModel):
    """Modelo base para todos los eventos transmitidos por WebSocket."""
    event_type: EventType
    task_id: str
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = {}


class TaskProgressEvent(WebSocketEvent):
    """Evento de actualización de progreso de tarea."""
    percentage: int
    status: TaskStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    
    @validator("event_type", pre=True, always=True)
    def set_event_type(cls, v):
        return EventType.PROGRESS_UPDATED


class TaskStatusEvent(WebSocketEvent):
    """Evento de cambio de estado de una tarea."""
    previous_status: Optional[TaskStatus] = None
    current_status: TaskStatus
    message: str
    
    @validator("event_type", pre=True)
    def set_event_type(cls, v, values):
        if "current_status" in values:
            status = values["current_status"]
            if status == TaskStatus.COMPLETED:
                return EventType.TASK_COMPLETED
            elif status == TaskStatus.FAILED:
                return EventType.TASK_FAILED
            elif status == TaskStatus.CANCELLED:
                return EventType.TASK_CANCELLED
        return EventType.TASK_UPDATED


class ErrorEvent(WebSocketEvent):
    """Evento de error."""
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    
    @validator("event_type", pre=True, always=True)
    def set_event_type(cls, v):
        return EventType.ERROR


class ProcessingMilestoneEvent(WebSocketEvent):
    """Evento para un hito específico en el procesamiento."""
    milestone: str
    message: str
    details: Optional[Dict[str, Any]] = None
    
    @validator("event_type", pre=True)
    def set_event_type(cls, v, values):
        if "milestone" in values:
            milestone = values["milestone"]
            if milestone == "document_received":
                return EventType.DOCUMENT_RECEIVED
            elif milestone == "text_extracted":
                return EventType.TEXT_EXTRACTED
            elif milestone == "chunking_completed":
                return EventType.CHUNKING_COMPLETED
            elif milestone == "embedding_started":
                return EventType.EMBEDDING_STARTED
            elif milestone == "embedding_completed":
                return EventType.EMBEDDING_COMPLETED
        return EventType.INFO
