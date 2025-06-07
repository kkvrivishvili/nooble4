"""
Worker principal para procesamiento asíncrono de documentos.

Este módulo implementa un worker que:
- Escucha colas Redis para obtener tareas
- Procesa documentos y extrae su contenido
- Divide documentos en chunks
- Solicita embeddings al servicio externo
- Actualiza el progreso en tiempo real vía WebSockets
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple

from common.context import create_context, Context, with_context
from common.errors import ServiceError, ErrorCode
from ingestion_service.config.settings import get_settings
from ingestion_service.models.actions import (
    DocumentProcessAction, DocumentChunkAction,
    EmbeddingRequestAction, EmbeddingCallbackAction,
    TaskStatusAction, TaskCancelAction
)
from ingestion_service.models.tasks import TaskStatus, TaskProgress
from ingestion_service.services.queue import queue_service
from ingestion_service.services.chunking import chunking_service
from ingestion_service.clients.embedding_client import embedding_client
from ingestion_service.websockets.event_dispatcher import event_dispatcher

settings = get_settings()
logger = logging.getLogger(__name__)


class IngestionWorker:
    """Worker para procesamiento asíncrono de documentos."""
    
    def __init__(self, worker_id: str = None):
        """Inicializa un nuevo worker.
        
        Args:
            worker_id: Identificador único para el worker
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"
        self.running = False
        self.context = create_context(component="ingestion_worker", worker_id=self.worker_id)
        self.sleep_time = settings.WORKER_SLEEP_TIME
        
    async def start(self):
        """Inicia el worker para escuchar las colas configuradas."""
        self.running = True
        logger.info(f"Iniciando worker {self.worker_id}")
        
        # Manejar múltiples colas en paralelo
        tasks = [
            self._listen_queue(settings.DOCUMENT_QUEUE, DocumentProcessAction),
            self._listen_queue(settings.EMBEDDING_CALLBACK_QUEUE, EmbeddingCallbackAction),
            self._listen_queue(settings.TASK_STATUS_QUEUE, TaskStatusAction)
        ]
        
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Detiene el worker de forma ordenada."""
        logger.info(f"Deteniendo worker {self.worker_id}")
        self.running = False
        
    @with_context
    async def _listen_queue(
        self, 
        queue: str, 
        action_type: Any,
        ctx: Optional[Context] = None
    ):
        """Escucha una cola específica y procesa las acciones recibidas.
        
        Args:
            queue: Nombre de la cola a escuchar
            action_type: Tipo de acción esperada
            ctx: Contexto de la operación
        """
        logger.info(f"Worker {self.worker_id} escuchando cola {queue}")
        
        while self.running:
            try:
                # Intentar obtener una acción de la cola
                action = await queue_service.dequeue_as_type(queue, action_type, timeout=1, ctx=ctx)
                
                if action:
                    # Enriquecer el contexto con información de la tarea
                    task_ctx = ctx.with_values(
                        task_id=action.task_id,
                        tenant_id=getattr(action, 'tenant_id', None)
                    )
                    
                    # Procesar la acción según su tipo
                    if isinstance(action, DocumentProcessAction):
                        await self._process_document(action, task_ctx)
                    elif isinstance(action, EmbeddingCallbackAction):
                        await self._handle_embedding_callback(action, task_ctx)
                    elif isinstance(action, TaskStatusAction):
                        await self._handle_task_status(action, task_ctx)
                    elif isinstance(action, TaskCancelAction):
                        await self._handle_task_cancel(action, task_ctx)
                    else:
                        logger.warning(
                            f"Acción de tipo {type(action).__name__} recibida en cola {queue} "
                            f"pero no está implementada"
                        )
                        
            except Exception as e:
                logger.error(f"Error en worker {self.worker_id}: {e}")
                # Breve pausa para evitar ciclos infinitos de errores
                await asyncio.sleep(self.sleep_time)
            
            # Pequeña pausa para no saturar CPU
            await asyncio.sleep(self.sleep_time)
    
    @with_context
    async def _process_document(
        self, 
        action: DocumentProcessAction,
        ctx: Context
    ):
        """Procesa un documento completo.
        
        Args:
            action: Acción de procesamiento de documento
            ctx: Contexto de la operación
        """
        task_id = action.task_id
        tenant_id = action.tenant_id
        document_id = action.document_id
        collection_id = action.collection_id
        
        logger.info(f"Procesando documento {document_id} para tarea {task_id}")
        
        try:
            # 1. Notificar inicio de procesamiento
            await event_dispatcher.send_status_update(
                task_id=task_id,
                tenant_id=tenant_id,
                current_status=TaskStatus.PROCESSING,
                message="Iniciando procesamiento del documento",
                ctx=ctx
            )
            
            # 2. Verificar origen del documento y extraer texto
            text_content = None
            
            # Hito: documento recibido (10%)
            await event_dispatcher.send_processing_milestone(
                task_id=task_id,
                tenant_id=tenant_id,
                milestone="document_received",
                message="Documento recibido para procesamiento",
                percentage=10,
                details={"document_id": document_id},
                ctx=ctx
            )
            
            # TODO: Implementar extracción del texto según el origen
            # Por ahora usamos el texto proporcionado directamente
            if action.text_content:
                text_content = action.text_content
            else:
                # Simulamos extracción para el ejemplo
                text_content = f"Contenido simulado para documento {document_id}"
                await asyncio.sleep(1)  # Simular tiempo de procesamiento
            
            # Hito: texto extraído (30%)
            await event_dispatcher.send_processing_milestone(
                task_id=task_id,
                tenant_id=tenant_id,
                milestone="text_extracted",
                message="Texto extraído correctamente",
                percentage=30,
                details={
                    "document_id": document_id,
                    "text_length": len(text_content)
                },
                ctx=ctx
            )
            
            # 3. Dividir en chunks
            logger.info(f"Fragmentando documento {document_id}")
            chunks = await chunking_service.split_document_intelligently(
                text=text_content,
                document_id=document_id,
                metadata={
                    "document_id": document_id,
                    "collection_id": collection_id,
                    "tenant_id": tenant_id,
                    "title": action.title
                },
                chunk_size=action.chunk_size,
                chunk_overlap=action.chunk_overlap,
                ctx=ctx
            )
            
            # Hito: chunking completado (60%)
            await event_dispatcher.send_processing_milestone(
                task_id=task_id,
                tenant_id=tenant_id,
                milestone="chunking_completed",
                message=f"Documento dividido en {len(chunks)} fragmentos",
                percentage=60,
                details={
                    "document_id": document_id,
                    "chunk_count": len(chunks)
                },
                ctx=ctx
            )
            
            # 4. Solicitar embeddings
            logger.info(f"Solicitando embeddings para {len(chunks)} chunks del documento {document_id}")
            
            # Crear acción para solicitar embeddings
            embedding_action = EmbeddingRequestAction(
                document_id=document_id,
                collection_id=collection_id,
                tenant_id=tenant_id,
                chunks=chunks,
                model=action.embedding_model,
                task_id=task_id,
                callback_queue=settings.EMBEDDING_CALLBACK_QUEUE
            )
            
            # Hito: embeddings solicitados (80%)
            await event_dispatcher.send_processing_milestone(
                task_id=task_id,
                tenant_id=tenant_id,
                milestone="embedding_started",
                message="Solicitando generación de embeddings",
                percentage=80,
                details={
                    "document_id": document_id,
                    "chunk_count": len(chunks),
                    "model": action.embedding_model
                },
                ctx=ctx
            )
            
            # Enviar solicitud al servicio de embeddings
            await embedding_client.generate_embeddings(embedding_action, ctx)
            
            # El procesamiento continuará cuando recibamos el callback
            
        except Exception as e:
            logger.error(f"Error al procesar documento {document_id}: {e}")
            
            # Notificar error por WebSocket
            await event_dispatcher.send_error(
                task_id=task_id,
                tenant_id=tenant_id,
                error_code="DOCUMENT_PROCESSING_ERROR",
                error_message=f"Error al procesar documento: {str(e)}",
                details={
                    "document_id": document_id,
                    "error": str(e)
                },
                ctx=ctx
            )
            
            # Actualizar estado en Redis
            await queue_service.set_task_failed(
                task_id=task_id,
                error=f"Error al procesar documento: {str(e)}",
                ctx=ctx
            )
    
    @with_context
    async def _handle_embedding_callback(
        self, 
        action: EmbeddingCallbackAction,
        ctx: Context
    ):
        """Maneja el callback con los embeddings generados.
        
        Args:
            action: Acción de callback con embeddings
            ctx: Contexto de la operación
        """
        task_id = action.task_id
        tenant_id = action.tenant_id
        document_id = action.document_id
        collection_id = action.collection_id
        
        logger.info(
            f"Recibido callback de embeddings para documento {document_id}, "
            f"estado: {action.status}"
        )
        
        try:
            if action.status == "success" and action.embeddings:
                # Hito: embeddings completados (90%)
                await event_dispatcher.send_processing_milestone(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    milestone="embedding_completed",
                    message="Embeddings generados correctamente",
                    percentage=90,
                    details={
                        "document_id": document_id,
                        "embedding_count": len(action.embeddings),
                        "dimension": len(action.embeddings[0]) if action.embeddings else 0
                    },
                    ctx=ctx
                )
                
                # TODO: Guardar embeddings en base de datos vectorial
                # Simulamos almacenamiento
                await asyncio.sleep(1)
                
                # Marcar tarea como completada
                await queue_service.set_task_completed(
                    task_id=task_id,
                    result={
                        "document_id": document_id,
                        "collection_id": collection_id,
                        "embedding_count": len(action.embeddings),
                        "dimension": len(action.embeddings[0]) if action.embeddings else 0
                    },
                    ctx=ctx
                )
                
                # Notificar finalización
                await event_dispatcher.send_status_update(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    current_status=TaskStatus.COMPLETED,
                    message="Documento procesado y almacenado correctamente",
                    ctx=ctx
                )
                
                # Actualizar progreso final (100%)
                await event_dispatcher.send_progress_update(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    percentage=100,
                    status=TaskStatus.COMPLETED,
                    message="Procesamiento completado correctamente",
                    details={
                        "document_id": document_id,
                        "embedding_count": len(action.embeddings)
                    },
                    ctx=ctx
                )
                
            else:
                # Manejar error en generación de embeddings
                error_msg = action.error or "Error desconocido en generación de embeddings"
                
                await event_dispatcher.send_error(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    error_code="EMBEDDING_ERROR",
                    error_message=error_msg,
                    details={
                        "document_id": document_id,
                        "status": action.status
                    },
                    ctx=ctx
                )
                
                # Marcar tarea como fallida
                await queue_service.set_task_failed(
                    task_id=task_id,
                    error=error_msg,
                    ctx=ctx
                )
                
        except Exception as e:
            logger.error(f"Error al procesar callback de embeddings: {e}")
            
            # Notificar error
            await event_dispatcher.send_error(
                task_id=task_id,
                tenant_id=tenant_id,
                error_code="CALLBACK_PROCESSING_ERROR",
                error_message=f"Error al procesar callback: {str(e)}",
                details={"document_id": document_id},
                ctx=ctx
            )
            
            # Marcar tarea como fallida
            await queue_service.set_task_failed(
                task_id=task_id,
                error=f"Error al procesar callback: {str(e)}",
                ctx=ctx
            )
    
    @with_context
    async def _handle_task_status(
        self, 
        action: TaskStatusAction,
        ctx: Context
    ):
        """Maneja una consulta de estado de tarea.
        
        Args:
            action: Acción de consulta de estado
            ctx: Contexto de la operación
        """
        task_id = action.task_id
        logger.info(f"Consultando estado de tarea {task_id}")
        
        # Obtener estado actual de Redis
        status = await queue_service.get_task_status(task_id, ctx)
        
        # TODO: Implementar respuesta según se requiera
        logger.info(f"Estado de tarea {task_id}: {status}")
    
    @with_context
    async def _handle_task_cancel(
        self, 
        action: TaskCancelAction,
        ctx: Context
    ):
        """Maneja la cancelación de una tarea.
        
        Args:
            action: Acción de cancelación
            ctx: Contexto de la operación
        """
        task_id = action.task_id
        tenant_id = action.tenant_id
        
        logger.info(f"Solicitada cancelación de tarea {task_id}")
        
        # TODO: Implementar lógica de cancelación
        # Por ahora solo notificamos
        
        await event_dispatcher.send_status_update(
            task_id=task_id,
            tenant_id=tenant_id,
            current_status=TaskStatus.CANCELLED,
            message="Tarea cancelada por solicitud del usuario",
            ctx=ctx
        )
        
        # Actualizar estado en Redis
        await queue_service.set_task_failed(
            task_id=task_id,
            error="Tarea cancelada por solicitud del usuario",
            ctx=ctx
        )
