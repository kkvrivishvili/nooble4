import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid

from qdrant_client import AsyncQdrantClient

from common.services import BaseService
from common.models import DomainAction, DomainActionResponse
from common.config import CommonAppSettings
from common.clients import BaseRedisClient, RedisStateManager
from redis.asyncio import Redis as AIORedis

from ..models import (
    DocumentIngestionRequest, IngestionTask, IngestionStatus,
    ProcessingProgress, ChunkModel
)
from ..handlers import (
    DocumentProcessorHandler, ChunkEnricherHandler, QdrantHandler
)
from ..websocket.manager import WebSocketManager


class IngestionService(BaseService):
    """Main service for document ingestion"""
    
    def __init__(
        self,
        app_settings: CommonAppSettings,
        service_redis_client: BaseRedisClient,
        direct_redis_conn: AIORedis
    ):
        super().__init__(app_settings, service_redis_client, direct_redis_conn)
        
        # NUEVO: Cliente Qdrant a nivel de servicio
        self.qdrant_client = AsyncQdrantClient(
            url=str(app_settings.qdrant_url),
            api_key=app_settings.qdrant_api_key
        )
        
        # Initialize handlers
        self.document_processor = DocumentProcessorHandler(app_settings)
        self.chunk_enricher = ChunkEnricherHandler(app_settings)
        
        # CAMBIO: Inyectar el cliente Qdrant al handler
        self.qdrant_handler = QdrantHandler(
            app_settings=app_settings,
            qdrant_client=self.qdrant_client
        )
        
        # State managers
        self.task_state_manager = RedisStateManager[IngestionTask](
            redis_conn=direct_redis_conn,
            state_model=IngestionTask,
            app_settings=app_settings
        )
        
        # WebSocket manager for progress updates
        self.ws_manager = WebSocketManager()
        
        self._logger.info("IngestionService initialized")
    
    async def process_action(self, action: DomainAction) -> Optional[Dict[str, Any]]:
        """Process incoming domain actions"""
        try:
            action_type = action.action_type.split('.')[-1]  # Get last part
            
            if action_type == "ingest_document":
                return await self._handle_ingest_document(action)
            elif action_type == "embedding_result":
                return await self._handle_embedding_result(action)
            elif action_type == "get_status":
                return await self._handle_get_status(action)
            elif action_type == "delete_document":
                return await self._handle_delete_document(action)
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")
                
        except Exception as e:
            self._logger.error(f"Error processing action: {e}")
            raise
    
    async def _handle_ingest_document(self, action: DomainAction) -> Dict[str, Any]:
        """Handle document ingestion request"""
        # Parse request
        request = DocumentIngestionRequest(**action.data)
        
        # NUEVO: Validar agent_id
        if not request.agent_id:
            raise ValueError("agent_id is required for document ingestion")
        
        # NUEVO: Validar rag_config
        if not action.rag_config:
            raise ValueError("rag_config is required for document ingestion")
        
        self._logger.info(
            f"Starting document ingestion for agent_id={request.agent_id}, "
            f"document={request.document_name}, tenant={request.tenant_id}"
        )
        
        # Define la duración del timeout para la tarea (idealmente desde app_settings)
        task_timeout_hours = getattr(self.app_settings, 'ingestion_task_timeout_hours', 2)

        # Create task CON agent_id y expires_at
        task = IngestionTask(
            task_id=str(action.task_id),
            tenant_id=action.tenant_id,
            user_id=action.user_id,
            session_id=action.session_id,
            agent_id=request.agent_id,  # NUEVO: Incluir agent_id
            request=request,
            status=IngestionStatus.PROCESSING,
            expires_at=datetime.utcnow() + timedelta(hours=task_timeout_hours)
        )
        
        # Save task state
        await self.task_state_manager.save_state(
            f"task:{task.task_id}",
            task,
            expiration_seconds=86400  # 24 hours
        )
        
        # Start async processing CON rag_config
        asyncio.create_task(self._process_ingestion_task(task, action))
        
        return {
            "task_id": task.task_id,
            "document_id": task.document_id,
            "status": task.status.value,
            "agent_id": task.agent_id,  # NUEVO: Incluir en respuesta
            "message": "Document ingestion started"
        }
    
    async def _process_ingestion_task(self, task: IngestionTask, original_action: DomainAction):
        """Process the ingestion task asynchronously"""
        try:
            # Update progress: Processing
            await self._update_progress(task, IngestionStatus.PROCESSING, "Loading document", 10)
            
            # CAMBIO: Process document into chunks CON agent_id
            chunks = await self.document_processor.process_document(
                task.request,
                task.document_id,
                agent_id=task.agent_id  # NUEVO: Propagar agent_id
            )
            task.total_chunks = len(chunks)
            
            # Update progress: Chunking
            await self._update_progress(task, IngestionStatus.CHUNKING, f"Created {len(chunks)} chunks", 30)
            
            # Enrich chunks with agent_id validation
            self._logger.info(f"Enriching {len(chunks)} chunks for agent_id={task.agent_id}")
            chunks = await self.chunk_enricher.enrich_chunks(chunks)
            
            # Update progress: Embedding
            await self._update_progress(task, IngestionStatus.EMBEDDING, "Generating embeddings", 50)
            
            # CAMBIO: Send chunks to embedding service in batches CON rag_config
            batch_size = 10
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                await self._send_chunks_for_embedding(batch, task, original_action)
            
            # State will be updated when embeddings are received
            
        except Exception as e:
            self._logger.error(f"Error processing task {task.task_id} for agent_id={task.agent_id}: {e}")
            await self._update_progress(
                task, 
                IngestionStatus.FAILED, 
                "Processing failed",
                task.processed_chunks / task.total_chunks * 100 if task.total_chunks > 0 else 0,
                error=str(e)
            )
    
    async def _send_chunks_for_embedding(
        self, 
        chunks: List[ChunkModel], 
        task: IngestionTask,
        original_action: DomainAction
    ):
        """Send chunks to embedding service"""
        # Prepare texts for embedding
        texts = [chunk.content for chunk in chunks]  # CAMBIO CRÍTICO: text → content
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        
        # NUEVO: Extraer configuración del embedding desde rag_config
        embedding_model = original_action.rag_config.embedding_model
        
        self._logger.info(
            f"Sending {len(chunks)} chunks for embedding using model={embedding_model} for agent_id={task.agent_id}"
        )
        
        # Create action for embedding service CON rag_config en header
        embedding_action = DomainAction(
            action_type="embedding.batch.process",
            tenant_id=task.tenant_id,
            session_id=task.session_id,
            task_id=uuid.UUID(task.task_id),
            user_id=task.user_id,
            origin_service=self.service_name,
            trace_id=original_action.trace_id,
            rag_config=original_action.rag_config,  # NUEVO: Propagar rag_config
            data={
                "texts": texts,
                "chunk_ids": chunk_ids,
                "agent_id": task.agent_id  # NUEVO: Incluir agent_id en datos
            },
            metadata={
                "batch_index": chunks[0].chunk_index,
                "batch_size": len(chunks),
                "agent_id": task.agent_id  # NUEVO: También en metadata
            }
        )
        
        # Send with callback usando service_redis_client
        await self.service_redis_client.send_action_async_with_callback(
            embedding_action,
            callback_event_name="ingestion.embedding_result"
        )
    
    async def _handle_embedding_result(self, action: DomainAction) -> None:
        """Handle embedding results from embedding service"""
        data = action.data
        task_id = data.get("task_id")
        chunk_ids = data.get("chunk_ids", [])
        embeddings = data.get("embeddings", [])
        
        # NUEVO: Extraer agent_id desde metadata o data
        agent_id = data.get("agent_id") or action.metadata.get("agent_id")
        
        if not task_id:
            self._logger.error("No task_id in embedding result")
            return
            
        if not agent_id:
            self._logger.error(f"No agent_id in embedding result for task {task_id}")
            return
        
        # Load task
        task = await self.task_state_manager.load_state(f"task:{task_id}")
        if not task:
            self._logger.error(f"Task {task_id} not found")
            return
            
        # NUEVO: Validar que agent_id coincida
        if task.agent_id != agent_id:
            self._logger.error(
                f"Task {task_id}: agent_id mismatch - task has {task.agent_id}, "
                f"embedding result has {agent_id}"
            )
            return
        
        self._logger.info(
            f"Processing embedding results for task {task_id}, agent_id={agent_id}, "
            f"{len(chunk_ids)} chunks"
        )
        
        # Process embeddings
        chunks_to_store = []
        if len(chunk_ids) != len(embeddings):
            error_message = f"Critical mismatch: received {len(embeddings)} embeddings for {len(chunk_ids)} chunks."
            self._logger.error(f"Task {task_id}: {error_message}")
            
            task.status = IngestionStatus.FAILED
            task.error_message = error_message
            task.completed_at = datetime.utcnow()
            
            await self._update_progress(
                task,
                IngestionStatus.FAILED,
                "Task failed due to embedding count mismatch",
                task.processed_chunks / task.total_chunks * 100, # Progress so far
                error=error_message
            )
            
            await self.task_state_manager.save_state(f"task:{task.task_id}", task)
            return

        for i, chunk_id in enumerate(chunk_ids):
            embedding_result_dict = embeddings[i]
            error_detail = embedding_result_dict.get("error")

            if error_detail:
                self._logger.error(
                    f"Task {task_id}, Chunk {chunk_id}: Received error from embedding service.",
                    extra={"error": error_detail, "chunk_id": chunk_id, "task_id": task_id}
                )
                task.failed_chunks += 1
                await self.direct_redis_conn.delete(f"chunk:{chunk_id}") # Clean up
                continue

            actual_embedding_vector = embedding_result_dict.get("embedding")
            if actual_embedding_vector is None:
                self._logger.warning(f"Task {task_id}, Chunk {chunk_id}: Embedding result missing 'embedding' vector and no error reported.")
                task.failed_chunks += 1
                await self.direct_redis_conn.delete(f"chunk:{chunk_id}") # Clean up
                continue

            # Load chunk
            chunk_data = await self.direct_redis_conn.get(f"chunk:{chunk_id}")
            if chunk_data:
                try:
                    chunk = ChunkModel.parse_raw(chunk_data)
                    chunk.embedding = actual_embedding_vector
                    chunks_to_store.append(chunk)
                    
                    # Clean up temp storage
                    await self.direct_redis_conn.delete(f"chunk:{chunk_id}")
                except Exception as e:
                    self._logger.error(f"Task {task_id}, Chunk {chunk_id}: Failed to process chunk after embedding: {e}", exc_info=True)
                    task.failed_chunks += 1
            else:
                self._logger.warning(f"Task {task_id}: Chunk {chunk_id} not found in Redis for embedding result.")
                task.failed_chunks += 1

        # Store in Qdrant CON agent_id
        if chunks_to_store:
            await self._update_progress(task, IngestionStatus.STORING, "Storing vectors", 80)
            
            self._logger.info(f"Storing {len(chunks_to_store)} chunks in Qdrant for agent_id={agent_id}")
            result = await self.qdrant_handler.store_chunks(chunks_to_store)
            task.processed_chunks += result["stored"]
            
            # Check if complete
            if (task.processed_chunks + task.failed_chunks) >= task.total_chunks:
                task.status = IngestionStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.result = {
                    "document_id": task.document_id,
                    "total_chunks": task.total_chunks,
                    "stored_chunks": task.processed_chunks,
                    "failed_chunks": task.failed_chunks
                }
                
                await self._update_progress(
                    task, 
                    IngestionStatus.COMPLETED,
                    "Ingestion completed successfully",
                    100
                )
            else:
                # Update progress
                progress = (task.processed_chunks / task.total_chunks) * 100
                await self._update_progress(
                    task,
                    task.status,
                    f"Processed {task.processed_chunks}/{task.total_chunks} chunks",
                    progress
                )
            
            # Save updated task
            await self.task_state_manager.save_state(
                f"task:{task.task_id}",
                task,
                expiration_seconds=86400
            )
    
    async def _handle_get_status(self, action: DomainAction) -> Dict[str, Any]:
        """Get status of an ingestion task"""
        task_id = action.data.get("task_id")
        if not task_id:
            raise ValueError("task_id is required")
        
        task = await self.task_state_manager.load_state(f"task:{task_id}")
        if not task:
            return {
                "task_id": task_id,
                "status": "not_found",
                "error": "Task not found"
            }
        
        return {
            "task_id": task.task_id,
            "document_id": task.document_id,
            "status": task.status.value,
            "total_chunks": task.total_chunks,
            "processed_chunks": task.processed_chunks,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result,
            "error": task.error_message
        }
    
    async def _handle_delete_document(self, action: DomainAction) -> Dict[str, Any]:
        """Delete a document and its chunks"""
        document_id = action.data.get("document_id")
        agent_id = action.data.get("agent_id")

        if not document_id or not agent_id:
            raise ValueError("document_id and agent_id are required for deletion")

        self._logger.info(
            f"Deleting document {document_id} for agent_id={agent_id}, tenant={action.tenant_id}"
        )

        deleted_count = await self.qdrant_handler.delete_document(
            tenant_id=action.tenant_id,
            agent_id=agent_id,
            document_id=document_id
        )

        return {
            "document_id": document_id,
            "agent_id": agent_id,
            "deleted_chunks": deleted_count,
            "status": "deleted"
        }
    
    async def _update_progress(
        self,
        task: IngestionTask,
        status: IngestionStatus,
        message: str,
        percentage: float,
        error: Optional[str] = None
    ):
        """Update task progress and notify via WebSocket"""
        task.status = status
        task.updated_at = datetime.utcnow()
        if error:
            task.error_message = error

        # Guardar el estado actualizado de la tarea
        await self.task_state_manager.save_state(
            f"task:{task.task_id}",
            task,
            expiration_seconds=86400  # Mantener el estado por 24h
        )

        # Notificar por WebSocket
        progress_update = ProcessingProgress(
            task_id=task.task_id,
            status=status,
            current_step=message,
            progress_percentage=round(percentage, 2),
            message=message,
            error=error
        )
        await self.ws_manager.broadcast(task.session_id, progress_update.model_dump_json())

    async def _task_sweeper_loop(self):
        """Periodically checks for and fails expired tasks."""
        # Idealmente, este intervalo es configurable
        sweep_interval_seconds = getattr(self.app_settings, 'ingestion_sweeper_interval_seconds', 300)
        
        self._logger.info(f"Task sweeper started. Checking every {sweep_interval_seconds} seconds.")
        
        while True:
            await asyncio.sleep(sweep_interval_seconds)
            self._logger.info("Running task sweeper for expired tasks...")
            
            try:
                expired_tasks_count = 0
                # Use scan_iter to avoid blocking Redis with a potentially large number of keys
                async for task_key in self.direct_redis_conn.scan_iter("task:*"):
                    task_data = await self.direct_redis_conn.get(task_key)
                    if not task_data:
                        continue
                    
                    try:
                        task = IngestionTask.model_validate_json(task_data)
                    except Exception as e:
                        self._logger.warning(f"Could not parse task data for key {task_key}: {e}")
                        continue

                    # Check if task is in a terminal state
                    if task.status in [IngestionStatus.COMPLETED, IngestionStatus.FAILED]:
                        continue

                    # Check for expiration
                    if task.expires_at and datetime.utcnow() > task.expires_at:
                        self._logger.warning(
                            f"Task {task.task_id} for agent_id={task.agent_id} has expired. "
                            f"Marking as FAILED. Expiration was at {task.expires_at}."
                        )
                        
                        # Re-use the progress update logic to fail the task
                        await self._update_progress(
                            task,
                            IngestionStatus.FAILED,
                            "Task processing timed out.",
                            task.processed_chunks / task.total_chunks * 100 if task.total_chunks > 0 else 0,
                            error="Task exceeded the maximum configured processing time."
                        )
                        expired_tasks_count += 1

                if expired_tasks_count > 0:
                    self._logger.info(f"Task sweeper finished. Found and failed {expired_tasks_count} expired tasks.")
                else:
                    self._logger.info("Task sweeper finished. No expired tasks found.")

            except Exception as e:
                self._logger.error(f"Error during task sweeper run: {e}", exc_info=True)

    def start_background_tasks(self):
        """Starts all background tasks for the service."""
        self._logger.info("Scheduling background tasks...")
        asyncio.create_task(self._task_sweeper_loop())
        self._logger.info("Task sweeper has been scheduled.")

    async def _task_sweeper_loop(self):
        """Periodically checks for and fails expired tasks."""
        # Idealmente, este intervalo es configurable
        sweep_interval_seconds = getattr(self.app_settings, 'ingestion_sweeper_interval_seconds', 300)
        
        self._logger.info(f"Task sweeper started. Checking every {sweep_interval_seconds} seconds.")
        
        while True:
            await asyncio.sleep(sweep_interval_seconds)
            self._logger.info("Running task sweeper for expired tasks...")
            
            try:
                expired_tasks_count = 0
                # Use scan_iter to avoid blocking Redis with a potentially large number of keys
                async for task_key in self.direct_redis_conn.scan_iter("task:*"):
                    task_data = await self.direct_redis_conn.get(task_key)
                    if not task_data:
                        continue
                    
                    try:
                        task = IngestionTask.model_validate_json(task_data)
                    except Exception as e:
                        self._logger.warning(f"Could not parse task data for key {task_key}: {e}")
                        continue

                    # Check if task is in a terminal state
                    if task.status in [IngestionStatus.COMPLETED, IngestionStatus.FAILED]:
                        continue

                    # Check for expiration
                    if task.expires_at and datetime.utcnow() > task.expires_at:
                        self._logger.warning(
                            f"Task {task.task_id} for agent_id={task.agent_id} has expired. "
                            f"Marking as FAILED. Expiration was at {task.expires_at}."
                        )
                        
                        # Re-use the progress update logic to fail the task
                        await self._update_progress(
                            task,
                            IngestionStatus.FAILED,
                            "Task processing timed out.",
                            task.processed_chunks / task.total_chunks * 100 if task.total_chunks > 0 else 0,
                            error="Task exceeded the maximum configured processing time."
                        )
                        expired_tasks_count += 1

                if expired_tasks_count > 0:
                    self._logger.info(f"Task sweeper finished. Found and failed {expired_tasks_count} expired tasks.")
                else:
                    self._logger.info("Task sweeper finished. No expired tasks found.")

            except Exception as e:
                self._logger.error(f"Error during task sweeper run: {e}", exc_info=True)

    def start_background_tasks(self):
        """Starts all background tasks for the service."""
        self._logger.info("Scheduling background tasks...")
        asyncio.create_task(self._task_sweeper_loop())
        self._logger.info("Task sweeper has been scheduled.")


# ingestion_service/workers/__init__.py
"""Workers for Ingestion Service"""


__all__ = ["IngestionWorker"]