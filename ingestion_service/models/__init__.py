"""
Modelos utilizados por el servicio de ingestión.

Expone los modelos de acciones de dominio, eventos WebSocket y tareas de ingestión.
"""

from ingestion_service.models.actions import (
    IngestionTaskAction,
    IngestionProcessAction,
    IngestionCallbackAction,
    EmbeddingRequestAction
)
from ingestion_service.models.events import (
    TaskEvent,
    TaskCreatedEvent,
    TaskProgressEvent,
    TaskCompletedEvent,
    TaskFailedEvent
)
from ingestion_service.models.tasks import (
    Task,
    TaskStatus,
    TaskUpdate,
    TaskResult
)

__all__ = [
    # Actions
    'IngestionTaskAction',
    'IngestionProcessAction',
    'IngestionCallbackAction',
    'EmbeddingRequestAction',
    # Events
    'TaskEvent',
    'TaskCreatedEvent',
    'TaskProgressEvent',
    'TaskCompletedEvent',
    'TaskFailedEvent',
    # Tasks
    'Task',
    'TaskStatus',
    'TaskUpdate',
    'TaskResult'
]
