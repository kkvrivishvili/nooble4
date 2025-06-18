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
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

from common.context import create_context, Context, with_context
from common.errors import ServiceError, ErrorCode
from common.models.actions import DomainAction, DomainActionResponse, ErrorDetail, CollectionIngestionStatusAction, CollectionIngestionStatusData
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
from ingestion_service.clients.vector_store_client import vector_store_client, VectorDocument
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
        self.CALLBACK_INFO_TTL_SECONDS = 24 * 60 * 60  # 24 hours
        
    async def start(self):
        """Inicia el worker para escuchar las colas configuradas."""
        self.running = True
        logger.info(f"Iniciando worker {self.worker_id}")
        
        # Manejar múltiples colas en paralelo
        tasks = [
            self._listen_queue(settings.DOCUMENT_QUEUE, DocumentProcessAction),
            self._listen_queue(settings.EMBEDDING_CALLBACK_QUEUE, EmbeddingCallbackAction),
            self._listen_queue(settings.TASK_STATUS_QUEUE, TaskStatusAction),
            self._listen_domain_actions()
        ]
        
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Detiene el worker de forma ordenada."""

    async def _store_callback_info(self, task_id: str, callback_queue: str, correlation_id: Optional[str], action_type_response_to: str, ctx: Context):
        if not callback_queue:
            return
        # Assuming redis_client is available on self.context.redis_client or self.redis_client
        # This might need adjustment based on how BaseWorker provides redis_client
        redis_client = getattr(self.context, 'redis_client', None) or getattr(self, 'redis_client', None)
        if not redis_client:
            logger.error(f"Redis client not available for _store_callback_info. Task: {task_id}", extra=ctx.log_extra())
            return
            
        key = f"{settings.redis_prefix}:{settings.env_name}:ingestion:callback_info:{task_id}"
        payload = {
            "callback_queue": callback_queue,
            "correlation_id": correlation_id,
            "action_type_response_to": action_type_response_to
        }
        try:
            await redis_client.set(key, json.dumps(payload), ex=self.CALLBACK_INFO_TTL_SECONDS)
            logger.debug(f"Stored callback info for task {task_id} at {key}", extra=ctx.log_extra())
        except Exception as e:
            logger.error(f"Failed to store callback info for task {task_id}: {e}", extra=ctx.log_extra(), exc_info=True)

    async def _retrieve_callback_info(self, task_id: str, ctx: Context) -> Optional[Dict[str, Any]]:
        redis_client = getattr(self.context, 'redis_client', None) or getattr(self, 'redis_client', None)
        if not redis_client:
            logger.error(f"Redis client not available for _retrieve_callback_info. Task: {task_id}", extra=ctx.log_extra())
            return None

        key = f"{settings.redis_prefix}:{settings.env_name}:ingestion:callback_info:{task_id}"
        try:
            data_str = await redis_client.get(key)
            if data_str:
                await redis_client.delete(key) # Retrieve and delete
                logger.debug(f"Retrieved and deleted callback info for task {task_id} from {key}", extra=ctx.log_extra())
                return json.loads(data_str)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve callback info for task {task_id}: {e}", extra=ctx.log_extra(), exc_info=True)
            return None

    async def _send_sync_response(self, callback_queue: str, response_payload: Union[Dict[str, Any], DomainActionResponse], ctx: Context):
        if not callback_queue:
            logger.warning(f"Attempted to send sync response but callback_queue is None/empty.", extra=ctx.log_extra())
            return

        payload_to_send_dict = response_payload
        if isinstance(response_payload, DomainActionResponse):
            payload_to_send_dict = response_payload.dict(exclude_none=True)
        
        redis_client = getattr(self.context, 'redis_client', None) or getattr(self, 'redis_client', None)
        if not redis_client:
            logger.error(f"Redis client not available for _send_sync_response. Queue: {callback_queue}", extra=ctx.log_extra())
            return

        try:
            # This should ideally use a queue_manager method that handles serialization and queue name construction.
            # For now, direct rpush to the provided callback_queue name.
            await redis_client.rpush(callback_queue, json.dumps(payload_to_send_dict))
            logger.info(f"Sent sync response to {callback_queue}", extra=ctx.log_extra({"payload_preview": str(payload_to_send_dict)[:200]}))
        except Exception as e:
            logger.error(f"Failed to send sync response to {callback_queue}: {e}", extra=ctx.log_extra(), exc_info=True)

        logger.info(f"Deteniendo worker {self.worker_id}")
        self.running = False
        
    @with_context
    async def _handle_validate_collections(self, action: DomainAction, ctx: Context):
        """Handles the ingestion.collections.validate action."""
        collection_ids = action.data.get("collection_ids", [])
        tenant_id = action.tenant_id
        response_data = {"valid": False, "invalid_ids": collection_ids}
        success = False

        try:
            # Placeholder for actual validation logic with vector_store_client
            # This logic should check if all collection_ids exist for the tenant.
            # For now, we simulate a successful validation if collection_ids are present.
            # In a real implementation, you would call: 
            # validation_result = await vector_store_client.validate_collections_exist(collection_ids, tenant_id, ctx)
            valid_collections_result = {"valid": True, "invalid_ids": []}
            # Here you would implement the logic to check which IDs are invalid.
            response_data = valid_collections_result
            success = True
            logger.info(f"Validation result for tenant {tenant_id}: {response_data}", extra=ctx.log_extra())

        except Exception as e:
            logger.error(f"Error validating collections for tenant {tenant_id}: {e}", extra=ctx.log_extra(), exc_info=True)
            response_data["error"] = str(e)
        
        response = DomainActionResponse(
            success=success,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            data=response_data,
            error=None if success else ErrorDetail(error_code="VALIDATION_ERROR", message=response_data.get("error", "Unknown error"))
        )
        
        await self._send_sync_response(action.callback_queue_name, response, ctx)

    @with_context
    async def _handle_list_collections(self, action: DomainAction, ctx: Context):
        """Handles the ingestion.collections.list action."""
        tenant_id = action.tenant_id
        response_data = {"collections": []}
        success = False

        try:
            # Placeholder for actual listing logic with vector_store_client
            # collections = await vector_store_client.list_collections_for_tenant(tenant_id, ctx)
            # Simulating a response for now
            collections = [
                {"id": "sim-col-1", "name": "Simulated Collection 1"},
                {"id": "sim-col-2", "name": "Simulated Collection 2"}
            ]
            response_data["collections"] = collections
            success = True
            logger.info(f"Found {len(collections)} collections for tenant {tenant_id}", extra=ctx.log_extra())

        except Exception as e:
            logger.error(f"Error listing collections for tenant {tenant_id}: {e}", extra=ctx.log_extra(), exc_info=True)
            response_data["error"] = str(e)

        response = DomainActionResponse(
            success=success,
            correlation_id=action.correlation_id,
            trace_id=action.trace_id,
            action_type_response_to=action.action_type,
            data=response_data,
            error=None if success else ErrorDetail(error_code="LIST_ERROR", message=response_data.get("error", "Unknown error"))
        )
        
        await self._send_sync_response(action.callback_queue_name, response, ctx)

    @with_context
    async def _listen_domain_actions(self, ctx: Optional[Context] = None):
        """Listens to the domain actions queue and dispatches to handlers."""
        queue_name = settings.INGESTION_ACTIONS_QUEUE # Assumes INGESTION_ACTIONS_QUEUE is in settings
        logger.info(f"Worker {self.worker_id} listening for domain actions on queue {queue_name}")

        while self.running:
            try:
                message = await queue_service.dequeue(queue_name, timeout=1, ctx=ctx)
                if message:
                    try:
                        action = DomainAction.parse_raw(message)
                        
                        action_ctx = ctx.with_values(
                            action_id=action.action_id,
                            correlation_id=action.correlation_id,
                            tenant_id=action.tenant_id
                        )

                        if action.action_type == "ingestion.collections.validate":
                            await self._handle_validate_collections(action, action_ctx)
                        elif action.action_type == "ingestion.collections.list":
                            await self._handle_list_collections(action, action_ctx)
                        else:
                            logger.warning(f"Unknown domain action type received: {action.action_type}", extra=action_ctx.log_extra())

                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"Failed to parse DomainAction from message: {message}. Error: {e}", extra=ctx.log_extra())

            except Exception as e:
                logger.error(f"Error in domain action listener on queue {queue_name}: {e}", extra=ctx.log_extra(), exc_info=True)
                await asyncio.sleep(self.sleep_time)
            
            await asyncio.sleep(0.1) # Shorter sleep time for responsive actions

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

        # Store callback info if provided for pseudo-synchronous response
        if action.callback_queue:
            await self._store_callback_info(
                task_id=task_id,
                callback_queue=action.callback_queue,
                correlation_id=action.correlation_id, # Propagated from DomainAction
                action_type_response_to=action.action_type, # From DomainAction
                ctx=ctx
            )
        
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
            
            await embedding_client.request_embeddings(
                task_id=task_id,
                document_id=document_id,
                collection_id=collection_id,
                tenant_id=tenant_id,
                session_id=action.session_id, # Propagate session_id
                chunks=[chunk.dict() for chunk in chunks],
                model=action.embedding_model,
                callback_queue=settings.EMBEDDING_CALLBACK_QUEUE,
                ctx=ctx
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
            

            
            # El procesamiento continuará cuando recibamos el callback
            
        except Exception as e:
            error_message = f"Error al procesar documento: {str(e)}"
            logger.error(f"Error al procesar documento {document_id}: {e}", exc_info=True)
            
            # Notificar error por WebSocket
            await event_dispatcher.send_error(
                task_id=task_id,
                tenant_id=tenant_id,
                error_code="DOCUMENT_PROCESSING_ERROR",
                error_message=error_message,
                details={
                    "document_id": document_id,
                    "error": str(e)
                },
                ctx=ctx
            )
            
            # Actualizar estado en Redis
            await queue_service.set_task_failed(
                task_id=task_id,
                error=error_message,
                ctx=ctx
            )

            # Notificar a AMS sobre el fallo
            await self._notify_ams_of_ingestion_status(
                task_id=task_id,
                tenant_id=tenant_id,
                collection_id=collection_id,
                status="FAILED",
                message=error_message,
                ctx=ctx,
            )

            # Send error response if callback info exists
            callback_info = await self._retrieve_callback_info(task_id, ctx)
            if callback_info:
                error_response = DomainActionResponse(
                    success=False,
                    correlation_id=callback_info.get("correlation_id"),
                    trace_id=action.trace_id, # Propagate from original action
                    action_type_response_to=callback_info.get("action_type_response_to"),
                    error=ErrorDetail(error_code="DOCUMENT_PROCESSING_ERROR", message=str(e))
                )
                await self._send_sync_response(callback_info["callback_queue"], error_response, ctx)
    
    @with_context
    async def _finalize_task(
        self,
        task_id: str,
        tenant_id: str,
        collection_id: str,
        status: TaskStatus,
        final_message: str,
        details: Dict[str, Any],
        ctx: Context,
    ):
        """Centralized method to finalize a task (complete or fail)."""
        logger.info(f"Finalizing task {task_id} with status {status.value}")

        if status == TaskStatus.COMPLETED:
            await queue_service.set_task_completed(task_id, result=details, ctx=ctx)
            await event_dispatcher.send_status_update(
                task_id, tenant_id, TaskStatus.COMPLETED, final_message, ctx
            )
            await event_dispatcher.send_progress_update(
                task_id, tenant_id, 100, TaskStatus.COMPLETED, final_message, details, ctx
            )
            ams_status = "COMPLETED"
        else: # FAILED or CANCELLED
            await queue_service.set_task_failed(task_id, error=final_message, ctx=ctx)
            await event_dispatcher.send_error(
                task_id, tenant_id, "INGESTION_FAILED", final_message, details, ctx
            )
            ams_status = "FAILED"

        # Notify AMS regardless of outcome
        await self._notify_ams_of_ingestion_status(
            task_id, tenant_id, collection_id, ams_status, final_message, ctx
        )

        # Handle pseudo-synchronous response if a callback was requested
        callback_info = await self._retrieve_callback_info(task_id, ctx)
        if callback_info:
            response = DomainActionResponse(
                success=(status == TaskStatus.COMPLETED),
                correlation_id=callback_info.get("correlation_id"),
                trace_id=ctx.trace_id,
                action_type_response_to=callback_info.get("action_type_response_to"),
                data=details if status == TaskStatus.COMPLETED else None,
                error=ErrorDetail(error_code="INGESTION_FAILED", message=final_message) if status != TaskStatus.COMPLETED else None,
            )
            await self._send_sync_response(callback_info["callback_queue"], response, ctx)

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
                
                # Guardar embeddings y chunks en base de datos vectorial
                if not action.chunks or len(action.chunks) != len(action.embeddings):
                    error_msg = "Mismatch between number of chunks and embeddings received, or chunks are missing."
                    logger.error(f"{error_msg} Task ID: {task_id}, Document ID: {document_id}")
                    await event_dispatcher.send_error(
                        task_id=task_id, tenant_id=tenant_id, error_code="EMBEDDING_DATA_MISMATCH",
                        error_message=error_msg, details={"document_id": document_id}, ctx=ctx
                    )
                    await queue_service.set_task_failed(task_id=task_id, error=error_msg, ctx=ctx)
                    # Send error response if callback info exists
                    callback_info_err_mismatch = await self._retrieve_callback_info(task_id, ctx)
                    if callback_info_err_mismatch:
                        error_resp = DomainActionResponse(
                            success=False,
                            correlation_id=callback_info_err_mismatch.get("correlation_id"),
                            trace_id=action.trace_id, # Assuming EmbeddingCallbackAction also has trace_id
                            action_type_response_to=callback_info_err_mismatch.get("action_type_response_to"),
                            error=ErrorDetail(error_code="EMBEDDING_DATA_MISMATCH", message=error_msg)
                        )
                        await self._send_sync_response(callback_info_err_mismatch["callback_queue"], error_resp, ctx)
                    return # Stop further processing for this callback

                vector_documents_to_add: List[VectorDocument] = []
                for i, embedding_vector in enumerate(action.embeddings):
                    chunk_data = action.chunks[i]
                    chunk_id = chunk_data.get("id") or chunk_data.get("chunk_id") # Prefer 'id', fallback to 'chunk_id'
                    if not chunk_id:
                        # If no ID, generate one, though ideally chunking service provides it
                        chunk_id = f"{document_id}_chunk_{i}"
                        logger.warning(f"Chunk missing an ID, generated: {chunk_id} for document {document_id}")

                    # Ensure essential metadata is present
                    chunk_metadata = chunk_data.get("metadata", {})
                    chunk_metadata.update({
                        "document_id": document_id,
                        "collection_id": collection_id,
                        "tenant_id": tenant_id,
                        "task_id": task_id
                    })

                    vector_doc = VectorDocument(
                        id=str(chunk_id),
                        text=chunk_data.get("text", ""),
                        embedding=embedding_vector,
                        metadata=chunk_metadata,
                        collection_name=collection_id, # Assuming collection_id is the target collection name
                        tenant_id=tenant_id
                    )
                    vector_documents_to_add.append(vector_doc)
                
                if vector_documents_to_add:
                    storage_result = await vector_store_client.add_documents(vector_documents_to_add)
                    if not storage_result.get("success"):
                        error_msg = f"Failed to store embeddings in vector store: {storage_result.get('error', 'Unknown error')}"
                        logger.error(f"{error_msg} Task ID: {task_id}, Document ID: {document_id}")
                        await event_dispatcher.send_error(
                            task_id=task_id, tenant_id=tenant_id, error_code="VECTOR_STORAGE_ERROR",
                            error_message=error_msg, details={"document_id": document_id}, ctx=ctx
                        )
                        await queue_service.set_task_failed(task_id=task_id, error=error_msg, ctx=ctx)
                        # Send error response if callback info exists
                        callback_info_err_storage = await self._retrieve_callback_info(task_id, ctx)
                        if callback_info_err_storage:
                            error_resp_storage = DomainActionResponse(
                                success=False,
                                correlation_id=callback_info_err_storage.get("correlation_id"),
                                trace_id=action.trace_id,
                                action_type_response_to=callback_info_err_storage.get("action_type_response_to"),
                                error=ErrorDetail(error_code="VECTOR_STORAGE_ERROR", message=error_msg)
                            )
                            await self._send_sync_response(callback_info_err_storage["callback_queue"], error_resp_storage, ctx)
                        return # Stop further processing
                    logger.info(f"Successfully stored {len(vector_documents_to_add)} embeddings for document {document_id} in collection {collection_id}.")
                else:
                    logger.warning(f"No vector documents were prepared for document {document_id}. This might indicate an issue.")
                
                # Finalize the task as COMPLETED
                final_details = {
                    "document_id": document_id,
                    "collection_id": collection_id,
                    "embedding_count": len(action.embeddings),
                    "dimension": len(action.embeddings[0]) if action.embeddings else 0,
                }
                await self._finalize_task(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    status=TaskStatus.COMPLETED,
                    final_message="Documento procesado y almacenado correctamente",
                    details=final_details,
                    ctx=ctx,
                )
                
            else:
                error_message = action.error or "Error desconocido durante la generación de embeddings"
                logger.error(
                    f"Error en callback de embeddings para documento {document_id}: {error_message}"
                )
                
                # Notificar error por WebSocket
                await event_dispatcher.send_error(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    error_code="EMBEDDING_GENERATION_ERROR",
                    error_message=error_message,
                    details={
                        "document_id": document_id,
                        "error": error_message
                    },
                    ctx=ctx
                )
                
                # Finalize the task as FAILED
                await self._finalize_task(
                    task_id=task_id,
                    tenant_id=tenant_id,
                    collection_id=collection_id,
                    status=TaskStatus.FAILED,
                    final_message=error_message,
                    details={"document_id": document_id, "error": error_message},
                    ctx=ctx,
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
            
            # Finalize the task as FAILED
            await self._finalize_task(
                task_id=task_id,
                tenant_id=tenant_id,
                collection_id=collection_id, # collection_id should be available here
                status=TaskStatus.FAILED,
                final_message=f"Error al procesar callback: {str(e)}",
                details={"document_id": document_id, "error": str(e)},
                ctx=ctx,
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

    @with_context
    async def _notify_ams_of_ingestion_status(
        self,
        task_id: str,
        tenant_id: str,
        collection_id: str,
        status: str,
        message: Optional[str],
        ctx: Context,
    ):
        """Notifies Agent Management Service about the final status of an ingestion for a collection."""
        logger.info(
            f"Notifying AMS about ingestion status for collection {collection_id} "
            f"(Task: {task_id}, Status: {status})"
        )
        try:
            action_data = CollectionIngestionStatusData(
                collection_id=collection_id,
                tenant_id=tenant_id,
                status=status,
                message=message,
            )
            
            action = CollectionIngestionStatusAction(
                action_id=f"ams-notify-{uuid.uuid4()}",
                correlation_id=ctx.correlation_id,
                trace_id=ctx.trace_id,
                tenant_id=tenant_id,
                user_id="system",
                source_service="ingestion_service",
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                data=action_data,
            )

            management_queue = settings.MANAGEMENT_ACTIONS_QUEUE
            await queue_service.enqueue(management_queue, action.json(), ctx=ctx)
            logger.info(f"Successfully enqueued notification to AMS for collection {collection_id} on queue {management_queue}")

        except Exception as e:
            logger.error(
                f"Failed to notify AMS for collection {collection_id}. Error: {e}",
                extra=ctx.log_extra(),
                exc_info=True,
            )
