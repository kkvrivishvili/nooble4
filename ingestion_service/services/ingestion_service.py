import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
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
        
        # Create task CON agent_id
        task = IngestionTask(
            task_id=str(action.task_id),
            tenant_id=action.tenant_id,
            user_id=action.user_id,
            session_id=action.session_id,
            agent_id=request.agent_id,  # NUEVO: Incluir agent_id
            request=request,
            status=IngestionStatus.PROCESSING
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
            self._logger.error(
                f"Task {task_id}: Mismatch between chunk_ids ({len(chunk_ids)}) and embeddings ({len(embeddings)}) count."
            )
            # Potentially mark task as failed or handle error appropriately
            return

        for i, chunk_id in enumerate(chunk_ids):
            embedding_result_dict = embeddings[i] # This is a dict like {"text_index": N, "embedding": [...], ...}
            actual_embedding_vector = embedding_result_dict.get("embedding")

            if actual_embedding_vector is None:
                self._logger.warning(f"Task {task_id}, Chunk {chunk_id}: No 'embedding' key in embedding_result_dict: {embedding_result_dict}")
                continue # Or handle as a failed chunk

            # Load chunk
            chunk_data = await self.direct_redis_conn.get(f"chunk:{chunk_id}")
            if chunk_data:
                try:
                    chunk = ChunkModel.model_validate_json(chunk_data)
                    
                    # NUEVO: Verificar que el chunk tiene el agent_id correcto
                    if chunk.agent_id != agent_id:
                        self._logger.warning(
                            f"Task {task_id}, Chunk {chunk_id}: agent_id mismatch - "
                            f"chunk has {chunk.agent_id}, expected {agent_id}"
                        )
                        continue
                        
                    chunk.embedding = actual_embedding_vector
                    chunks_to_store.append(chunk)
                    
                    # Clean up temp storage
                    await self.direct_redis_conn.delete(f"chunk:{chunk_id}")
                except Exception as e:
                    self._logger.error(f"Task {task_id}, Chunk {chunk_id}: Failed to process chunk after embedding: {e}", exc_info=True)
            else:
                self._logger.warning(f"Task {task_id}: Chunk {chunk_id} not found in Redis for embedding result.")
        
        # Store in Qdrant CON agent_id
        if chunks_to_store:
            await self._update_progress(task, IngestionStatus.STORING, "Storing vectors", 80)
            
            self._logger.info(f"Storing {len(chunks_to_store)} chunks in Qdrant for agent_id={agent_id}")
            result = await self.qdrant_handler.store_chunks(chunks_to_store)
            task.processed_chunks += result["stored"]
            
            # Check if complete
            if task.processed_chunks >= task.total_chunks:
                task.status = IngestionStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.result = {
                    "document_id": task.document_id,
                    "total_chunks": task.total_chunks,
                    "stored_chunks": task.processed_chunks
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
        if not document_id:
            raise ValueError("document_id is required")
        
        deleted_count = await self.qdrant_handler.delete_document(
            action.tenant_id,
            document_id
        )
        
        return {
            "document_id": document_id,
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
        
        # Create progress update
        progress = ProcessingProgress(
            task_id=task.task_id,
            status=status,
            current_step=status.value,
            progress_percentage=percentage,
            message=message,
            error=error,
            details={
                "document_id": task.document_id,
                "total_chunks": task.total_chunks,
                "processed_chunks": task.processed_chunks
            }
        )
        
        # Save task state
        await self.task_state_manager.save_state(
            f"task:{task.task_id}",
            task,
            expiration_seconds=86400
        )


# ingestion_service/workers/__init__.py
"""Workers for Ingestion Service"""


__all__ = ["IngestionWorker"]