"""
Endpoints REST para gestión y procesamiento de documentos.

Este módulo implementa las rutas para:
- Subir documentos y procesarlos
- Ingerir contenido desde URLs
- Procesar texto plano
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from common.context import with_context, Context, create_context
from common.errors import ValidationError, DocumentProcessingError, handle_error
from ingestion_service.config.settings import get_settings
from ingestion_service.models.actions import DocumentProcessAction
from ingestion_service.models.tasks import (
    TaskCreateRequest, TaskResponse, TaskListResponse, 
    TaskStatus, TaskType, TaskSource, Task, TaskProgress
)
from ingestion_service.services.queue import queue_service
from ingestion_service.services.chunking import chunking_service
from datetime import datetime

settings = get_settings()
logger = logging.getLogger(__name__)

# Crear router para las rutas de documentos
router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


# Contexto para las rutas
def get_request_context():
    """Crea un contexto para las solicitudes HTTP."""
    return create_context(component="api", operation="document_processing")


@router.post("/", response_model=TaskResponse)
@with_context
async def create_document_processing_task(
    tenant_id: str = Query(..., description="ID del tenant"),
    collection_id: str = Query(..., description="ID de la colección de documentos"),
    document_id: str = Query(..., description="ID del documento a procesar"),
    file: Optional[UploadFile] = File(None, description="Archivo a procesar"),
    url: Optional[str] = Form(None, description="URL a procesar"),
    text: Optional[str] = Form(None, description="Texto a procesar"),
    title: Optional[str] = Form(None, description="Título del documento"),
    description: Optional[str] = Form(None, description="Descripción del documento"),
    tags: Optional[str] = Form(None, description="Tags separados por comas"),
    chunk_size: Optional[int] = Form(None, description="Tamaño de los chunks"),
    chunk_overlap: Optional[int] = Form(None, description="Overlap entre chunks"),
    embedding_model: Optional[str] = Form(None, description="Modelo de embeddings a usar"),
    ctx: Context = Depends(get_request_context)
):
    """Crea una tarea de procesamiento de documento y la encola para procesamiento asíncrono.
    
    La tarea puede procesar un archivo subido, una URL o texto plano.
    """
    logger.info(f"Nueva solicitud de procesamiento de documento: tenant={tenant_id}, document={document_id}")
    
    try:
        # Validar que al menos una fuente de datos está presente
        if not file and not url and not text:
            raise ValidationError(
                message="Se debe proporcionar al menos una fuente de datos (file, url o text)",
                details={"error": "missing_source"}
            )
        
        # Determinar tipo y origen de la tarea
        task_type = TaskType.DOCUMENT_PROCESSING
        task_source = TaskSource.FILE if file else TaskSource.URL if url else TaskSource.TEXT
        
        # Generar ID de tarea
        task_id = str(uuid.uuid4())
        
        # Procesar tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Preparar metadatos
        metadata = {
            "title": title,
            "description": description,
            "source_type": task_source,
        }
        
        # Validar archivo si está presente
        file_key = None
        if file:
            # Validar archivo
            file_info = await chunking_service.validate_file(file, ctx)
            
            # TODO: Guardar archivo en storage y obtener file_key
            file_key = f"temp/{task_id}/{file.filename}"
            
            # Añadir metadatos del archivo
            metadata["file_info"] = {
                "filename": file.filename,
                "content_type": file_info["content_type"],
                "size": file_info["size"]
            }
        
        # Crear acción de procesamiento
        process_action = DocumentProcessAction(
            document_id=document_id,
            collection_id=collection_id,
            tenant_id=tenant_id,
            file_key=file_key,
            url=url,
            text_content=text,
            title=title,
            description=description,
            tags=tag_list,
            metadata=metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model or settings.EMBEDDING_MODEL,
            task_id=task_id,
            callback_queue=settings.EMBEDDING_CALLBACK_QUEUE
        )
        
        # Encolar la acción para procesamiento asíncrono
        await queue_service.enqueue(
            action=process_action,
            queue=settings.DOCUMENT_QUEUE,
            ctx=ctx
        )
        
        # Crear tarea
        task = Task(
            task_id=task_id,
            tenant_id=tenant_id,
            status=TaskStatus.PENDING,
            type=task_type,
            source=task_source,
            document_id=document_id,
            collection_id=collection_id,
            title=title,
            description=description,
            tags=tag_list,
            metadata=metadata,
            progress=TaskProgress(
                percentage=0,
                current_step="pending",
                message="Tarea creada, esperando procesamiento"
            ),
            created_at=datetime.utcnow()
        )
        
        # Responder inmediatamente con el task_id
        return TaskResponse(
            success=True,
            message="Documento enviado para procesamiento",
            task=task
        )
        
    except ValidationError as e:
        return handle_error(e, status_code=400)
    except Exception as e:
        logger.error(f"Error al crear tarea de procesamiento: {e}")
        return handle_error(e, status_code=500)


@router.post("/text", response_model=TaskResponse)
@with_context
async def process_text_document(
    request: Dict[str, Any] = Body(...),
    ctx: Context = Depends(get_request_context)
):
    """Procesa un documento de texto plano enviado en el cuerpo JSON."""
    
    try:
        # Extraer campos requeridos
        tenant_id = request.get("tenant_id")
        collection_id = request.get("collection_id")
        document_id = request.get("document_id")
        text = request.get("text")
        
        if not tenant_id or not collection_id or not document_id or not text:
            raise ValidationError(
                message="Faltan campos requeridos (tenant_id, collection_id, document_id, text)",
                details={"error": "missing_required_fields"}
            )
        
        # Generar ID de tarea
        task_id = str(uuid.uuid4())
        
        # Crear acción de procesamiento
        process_action = DocumentProcessAction(
            document_id=document_id,
            collection_id=collection_id,
            tenant_id=tenant_id,
            text_content=text,
            title=request.get("title"),
            description=request.get("description"),
            tags=request.get("tags"),
            metadata=request.get("metadata", {}),
            chunk_size=request.get("chunk_size"),
            chunk_overlap=request.get("chunk_overlap"),
            embedding_model=request.get("embedding_model") or settings.EMBEDDING_MODEL,
            task_id=task_id,
            callback_queue=settings.EMBEDDING_CALLBACK_QUEUE
        )
        
        # Encolar acción
        await queue_service.enqueue(
            action=process_action,
            queue=settings.DOCUMENT_QUEUE,
            ctx=ctx
        )
        
        # Crear tarea
        task = Task(
            task_id=task_id,
            tenant_id=tenant_id,
            status=TaskStatus.PENDING,
            type=TaskType.TEXT_PROCESSING,
            source=TaskSource.TEXT,
            document_id=document_id,
            collection_id=collection_id,
            title=request.get("title"),
            description=request.get("description"),
            tags=request.get("tags"),
            metadata=request.get("metadata", {}),
            progress=TaskProgress(
                percentage=0,
                current_step="pending",
                message="Procesando texto"
            ),
            created_at=datetime.utcnow()
        )
        
        return TaskResponse(
            success=True,
            message="Texto enviado para procesamiento",
            task=task
        )
        
    except ValidationError as e:
        return handle_error(e, status_code=400)
    except Exception as e:
        logger.error(f"Error al procesar texto: {e}")
        return handle_error(e, status_code=500)


@router.post("/url", response_model=TaskResponse)
@with_context
async def process_url_document(
    request: Dict[str, Any] = Body(...),
    ctx: Context = Depends(get_request_context)
):
    """Procesa un documento desde una URL enviada en el cuerpo JSON."""
    
    try:
        # Extraer campos requeridos
        tenant_id = request.get("tenant_id")
        collection_id = request.get("collection_id")
        document_id = request.get("document_id")
        url = request.get("url")
        
        if not tenant_id or not collection_id or not document_id or not url:
            raise ValidationError(
                message="Faltan campos requeridos (tenant_id, collection_id, document_id, url)",
                details={"error": "missing_required_fields"}
            )
        
        # Generar ID de tarea
        task_id = str(uuid.uuid4())
        
        # Crear acción de procesamiento
        process_action = DocumentProcessAction(
            document_id=document_id,
            collection_id=collection_id,
            tenant_id=tenant_id,
            url=url,
            title=request.get("title"),
            description=request.get("description"),
            tags=request.get("tags"),
            metadata=request.get("metadata", {}),
            chunk_size=request.get("chunk_size"),
            chunk_overlap=request.get("chunk_overlap"),
            embedding_model=request.get("embedding_model") or settings.EMBEDDING_MODEL,
            task_id=task_id,
            callback_queue=settings.EMBEDDING_CALLBACK_QUEUE
        )
        
        # Encolar acción
        await queue_service.enqueue(
            action=process_action,
            queue=settings.DOCUMENT_QUEUE,
            ctx=ctx
        )
        
        # Crear tarea
        task = Task(
            task_id=task_id,
            tenant_id=tenant_id,
            status=TaskStatus.PENDING,
            type=TaskType.URL_PROCESSING,
            source=TaskSource.URL,
            document_id=document_id,
            collection_id=collection_id,
            title=request.get("title"),
            description=request.get("description"),
            tags=request.get("tags"),
            metadata=request.get("metadata", {
                "url": url
            }),
            progress=TaskProgress(
                percentage=0,
                current_step="pending",
                message="Descargando URL"
            ),
            created_at=datetime.utcnow()
        )
        
        return TaskResponse(
            success=True,
            message="URL enviada para procesamiento",
            task=task
        )
        
    except ValidationError as e:
        return handle_error(e, status_code=400)
    except Exception as e:
        logger.error(f"Error al procesar URL: {e}")
        return handle_error(e, status_code=500)
