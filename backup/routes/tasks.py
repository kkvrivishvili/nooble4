"""
Endpoints REST para gestión y consulta de tareas de procesamiento.

Este módulo implementa las rutas para:
- Consultar estado de tareas
- Listar tareas por tenant o colección
- Cancelar tareas en proceso
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from fastapi.responses import JSONResponse

from common.context import with_context, Context, create_context
from common.errors import ValidationError, handle_error
from ingestion_service.config.settings import get_settings
from ingestion_service.models.actions import TaskStatusAction, TaskCancelAction
from ingestion_service.models.tasks import (
    TaskResponse, TaskListResponse, Task
)
from ingestion_service.services.queue import queue_service

settings = get_settings()
logger = logging.getLogger(__name__)

# Crear router para las rutas de tareas
router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    responses={404: {"description": "Not found"}},
)


# Contexto para las rutas
def get_request_context():
    """Crea un contexto para las solicitudes HTTP."""
    return create_context(component="api", operation="task_management")


@router.get("/{task_id}", response_model=TaskResponse)
@with_context
async def get_task_status(
    task_id: str = Path(..., description="ID de la tarea"),
    tenant_id: str = Query(..., description="ID del tenant"),
    ctx: Context = Depends(get_request_context)
):
    """Consulta el estado actual de una tarea por su ID."""
    logger.info(f"Consultando estado de tarea {task_id} para tenant {tenant_id}")
    
    try:
        # Crear acción para consultar estado
        status_action = TaskStatusAction(
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        # Consultar estado en Redis
        task_status = await queue_service.get_task_status(task_id, ctx)
        
        if not task_status:
            raise ValidationError(
                message=f"Tarea no encontrada: {task_id}",
                details={"error": "task_not_found"}
            )
        
        # Construir respuesta basada en los metadatos de Redis
        # En una implementación completa, esto vendría de una base de datos
        # por ahora simulamos con lo que tenemos en Redis
        
        status = task_status.get("status", "pending")
        
        # Construir objeto Task con la información disponible
        # En una implementación real, se buscaría en base de datos
        task = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "status": status,
            "type": task_status.get("domain", "unknown"),
            "source": "unknown",
            "progress": {
                "percentage": 0 if status == "pending" else 
                             100 if status == "completed" else 50,
                "current_step": status,
                "message": task_status.get("status", "En proceso")
            },
            "created_at": task_status.get("enqueued_at", ""),
            "updated_at": task_status.get("dequeued_at", ""),
            "completed_at": task_status.get("completed_at", ""),
            "error": task_status.get("error", None)
        }
        
        if "result" in task_status:
            task["result"] = task_status["result"]
        
        return TaskResponse(
            success=True,
            message="Estado de tarea recuperado",
            task=task
        )
        
    except ValidationError as e:
        return handle_error(e, status_code=404)
    except Exception as e:
        logger.error(f"Error al consultar estado de tarea: {e}")
        return handle_error(e, status_code=500)


@router.delete("/{task_id}", response_model=TaskResponse)
@with_context
async def cancel_task(
    task_id: str = Path(..., description="ID de la tarea"),
    tenant_id: str = Query(..., description="ID del tenant"),
    ctx: Context = Depends(get_request_context)
):
    """Cancela una tarea en proceso."""
    logger.info(f"Cancelando tarea {task_id} para tenant {tenant_id}")
    
    try:
        # Crear acción para cancelar tarea
        cancel_action = TaskCancelAction(
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        # Verificar si la tarea existe
        task_status = await queue_service.get_task_status(task_id, ctx)
        
        if not task_status:
            raise ValidationError(
                message=f"Tarea no encontrada: {task_id}",
                details={"error": "task_not_found"}
            )
        
        # Encolar acción de cancelación
        await queue_service.enqueue(
            action=cancel_action,
            queue=settings.TASK_STATUS_QUEUE,
            ctx=ctx
        )
        
        return TaskResponse(
            success=True,
            message="Solicitud de cancelación enviada",
            task={
                "task_id": task_id,
                "tenant_id": tenant_id,
                "status": "cancelling",
                "progress": {
                    "percentage": 0,
                    "current_step": "cancelling",
                    "message": "Cancelando tarea"
                }
            }
        )
        
    except ValidationError as e:
        return handle_error(e, status_code=404)
    except Exception as e:
        logger.error(f"Error al cancelar tarea: {e}")
        return handle_error(e, status_code=500)


@router.get("/", response_model=TaskListResponse)
@with_context
async def list_tasks(
    tenant_id: str = Query(..., description="ID del tenant"),
    collection_id: Optional[str] = Query(None, description="Filtrar por colección"),
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    page: int = Query(1, description="Número de página"),
    page_size: int = Query(10, description="Tamaño de página"),
    ctx: Context = Depends(get_request_context)
):
    """Lista tareas con filtros y paginación.
    
    En la implementación actual, esto es un placeholder ya que se requiere una base de datos
    para implementación completa.
    """
    logger.info(f"Listando tareas para tenant {tenant_id}")
    
    # En una implementación completa, buscaríamos en base de datos
    # Por ahora retornamos una respuesta simulada
    
    return TaskListResponse(
        success=True,
        message="Listado de tareas",
        tasks=[],  # En implementación real vendrían de base de datos
        total=0,
        page=page,
        page_size=page_size
    )
