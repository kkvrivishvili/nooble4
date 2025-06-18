"""
Despachador de eventos para WebSockets.

Este módulo se encarga de crear y enviar eventos a los clientes conectados
a través del sistema de WebSockets.
"""

import logging
from typing import Dict, Any, Optional

from ingestion_service.models.events import (
    WebSocketEvent, TaskProgressEvent, TaskStatusEvent,
    ErrorEvent, ProcessingMilestoneEvent, EventType
)
from ingestion_service.models.tasks import TaskStatus
from ingestion_service.websockets.connection_manager import connection_manager
from common.context import with_context, Context

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Despachador de eventos para WebSockets."""
    
    @with_context
    async def send_progress_update(
        self,
        task_id: str,
        tenant_id: str,
        percentage: int,
        status: TaskStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        ctx: Optional[Context] = None
    ) -> bool:
        """Envía una actualización de progreso para una tarea.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            percentage: Porcentaje de progreso (0-100)
            status: Estado actual de la tarea
            message: Mensaje descriptivo del progreso
            details: Detalles adicionales (opcional)
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se envió a al menos una conexión
        """
        event = TaskProgressEvent(
            task_id=task_id,
            tenant_id=tenant_id,
            percentage=percentage,
            status=status,
            message=message,
            details=details or {}
        )
        
        count = await connection_manager.broadcast_to_task(task_id, event, ctx)
        return count > 0
    
    @with_context
    async def send_status_update(
        self,
        task_id: str,
        tenant_id: str,
        current_status: TaskStatus,
        previous_status: Optional[TaskStatus] = None,
        message: str = "",
        ctx: Optional[Context] = None
    ) -> bool:
        """Envía una actualización de estado para una tarea.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            current_status: Nuevo estado de la tarea
            previous_status: Estado anterior (opcional)
            message: Mensaje descriptivo del cambio
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se envió a al menos una conexión
        """
        event = TaskStatusEvent(
            task_id=task_id,
            tenant_id=tenant_id,
            current_status=current_status,
            previous_status=previous_status,
            message=message or f"Task status changed to {current_status}"
        )
        
        count = await connection_manager.broadcast_to_task(task_id, event, ctx)
        return count > 0
    
    @with_context
    async def send_error(
        self,
        task_id: str,
        tenant_id: str,
        error_code: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
        ctx: Optional[Context] = None
    ) -> bool:
        """Envía una notificación de error para una tarea.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            error_code: Código del error
            error_message: Descripción del error
            details: Detalles adicionales del error
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se envió a al menos una conexión
        """
        event = ErrorEvent(
            task_id=task_id,
            tenant_id=tenant_id,
            error_code=error_code,
            error_message=error_message,
            details=details or {}
        )
        
        count = await connection_manager.broadcast_to_task(task_id, event, ctx)
        
        # También enviar una actualización de estado a failed
        await self.send_status_update(
            task_id=task_id,
            tenant_id=tenant_id,
            current_status=TaskStatus.FAILED,
            message=error_message,
            ctx=ctx
        )
        
        return count > 0
    
    @with_context
    async def send_processing_milestone(
        self,
        task_id: str,
        tenant_id: str,
        milestone: str,
        message: str,
        percentage: int,
        details: Optional[Dict[str, Any]] = None,
        ctx: Optional[Context] = None
    ) -> bool:
        """Envía una notificación de hito en el procesamiento.
        
        Args:
            task_id: ID de la tarea
            tenant_id: ID del tenant
            milestone: Nombre del hito (document_received, text_extracted, etc)
            message: Mensaje descriptivo del hito
            percentage: Porcentaje de progreso asociado
            details: Detalles adicionales
            ctx: Contexto de la operación
            
        Returns:
            bool: True si se envió a al menos una conexión
        """
        # Crear el evento de hito
        milestone_event = ProcessingMilestoneEvent(
            task_id=task_id,
            tenant_id=tenant_id,
            milestone=milestone,
            message=message,
            details=details or {}
        )
        
        # Determinar el estado de la tarea según el hito
        status = TaskStatus.PROCESSING
        if milestone == "document_received":
            status = TaskStatus.PROCESSING
        elif milestone == "text_extracted":
            status = TaskStatus.EXTRACTING
        elif milestone == "chunking_completed":
            status = TaskStatus.CHUNKING
        elif milestone == "embedding_started":
            status = TaskStatus.EMBEDDING
        elif milestone == "embedding_completed":
            status = TaskStatus.STORING
        
        # Enviar también una actualización de progreso
        progress_event = TaskProgressEvent(
            task_id=task_id,
            tenant_id=tenant_id,
            percentage=percentage,
            status=status,
            message=message,
            details=details or {}
        )
        
        # Enviar ambos eventos
        await connection_manager.broadcast_to_task(task_id, milestone_event, ctx)
        count = await connection_manager.broadcast_to_task(task_id, progress_event, ctx)
        
        return count > 0


# Instancia global del despachador de eventos
event_dispatcher = EventDispatcher()
