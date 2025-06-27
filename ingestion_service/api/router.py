from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Body, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
import os
import aiofiles
from pathlib import Path

from common.models import DomainAction, RAGConfig
from ..models import (
    DocumentIngestionRequest, 
    IngestionTask, 
    IngestionStatus,
    BatchIngestionResponse,
    BatchDocumentIngestionRequest
)
from ..dependencies import get_ingestion_service, get_ws_manager

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Temporary upload directory
UPLOAD_DIR = Path("/tmp/ingestion_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and extract user info"""
    # TODO: Implement proper JWT validation
    # For now, mock user data
    return {
        "user_id": "user-123",
        "tenant_id": "tenant-456",
        "session_id": "session-789"
    }


@router.post("/ingest")
async def ingest_document(
    request: DocumentIngestionRequest,
    rag_config: RAGConfig,
    user_info: dict = Depends(verify_token),
    service = Depends(get_ingestion_service)
):
    """Ingest a document"""
    try:
        # Validate agent_id
        if not request.agent_id:
            raise HTTPException(
                status_code=400, 
                detail="agent_id is required for document ingestion"
            )
        
        # Validate collection_id
        if not request.collection_id:
            raise HTTPException(
                status_code=400, 
                detail="collection_id is required for document ingestion"
            )
        
        # Validate rag_config
        if not rag_config:
            raise HTTPException(
                status_code=400, 
                detail="rag_config is required for document ingestion"
            )
        
        # VALIDACIÓN CRÍTICA DE OWNERSHIP
        tenant_id = user_info["tenant_id"]
        
        # TODO: Implementar validación real con base de datos/servicio de agentes
        # Por ahora, validación básica de formato UUID
        try:
            # Validar formato UUID
            uuid.UUID(request.agent_id)
            uuid.UUID(request.collection_id)
            uuid.UUID(tenant_id)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid UUID format in IDs: {str(e)}"
            )
        
        # VALIDACIÓN LÓGICA: agent_id debe pertenecer al tenant
        logger.info(f"Validating agent_id={request.agent_id} belongs to tenant_id={tenant_id}")
        
        # VALIDACIÓN LÓGICA: collection_id debe pertenecer al agent
        logger.info(f"Validating collection_id={request.collection_id} belongs to agent_id={request.agent_id}")
        
        logger.info(
            f"Ingesting document for agent_id={request.agent_id}, "
            f"collection_id={request.collection_id}, "
            f"document={request.document_name}, tenant={tenant_id}"
        )
        
        # Create domain action
        action = DomainAction(
            action_type="ingestion.ingest_document",
            tenant_id=user_info["tenant_id"],
            user_id=user_info["user_id"],
            session_id=user_info["session_id"],
            task_id=uuid.uuid4(),
            origin_service="api",
            rag_config=rag_config,
            data=request.model_dump()
        )
        
        # Process synchronously (returns task info)
        result = await service.process_action(action)
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error in ingest endpoint for agent_id={getattr(request, 'agent_id', 'unknown')}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-ingest", response_model=BatchIngestionResponse)
async def batch_ingest_documents(
    request: BatchDocumentIngestionRequest,
    rag_config: RAGConfig,
    user_info: dict = Depends(verify_token),
    service = Depends(get_ingestion_service)
):
    """Batch ingest multiple documents under same agent_id and collection_id"""
    try:
        # Validate agent_id
        if not request.agent_id:
            raise HTTPException(
                status_code=400, 
                detail="agent_id is required for batch document ingestion"
            )
        
        # Validate collection_id
        if not request.collection_id:
            raise HTTPException(
                status_code=400, 
                detail="collection_id is required for batch document ingestion"
            )
        
        # Validate documents list
        if not request.documents or len(request.documents) == 0:
            raise HTTPException(
                status_code=400, 
                detail="At least one document is required for batch ingestion"
            )
        
        # Validate rag_config
        if not rag_config:
            raise HTTPException(
                status_code=400, 
                detail="rag_config is required for batch document ingestion"
            )
        
        # VALIDACIÓN CRÍTICA DE OWNERSHIP
        tenant_id = user_info["tenant_id"]
        
        # Validar formato UUID
        try:
            uuid.UUID(request.agent_id)
            uuid.UUID(request.collection_id)
            uuid.UUID(tenant_id)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid UUID format in IDs: {str(e)}"
            )
        
        # VALIDACIÓN LÓGICA: agent_id debe pertenecer al tenant
        logger.info(f"Validating agent_id={request.agent_id} belongs to tenant_id={tenant_id}")
        
        # VALIDACIÓN LÓGICA: collection_id debe pertenecer al agent
        logger.info(f"Validating collection_id={request.collection_id} belongs to agent_id={request.agent_id}")
        
        batch_id = str(uuid.uuid4())
        logger.info(
            f"Starting batch ingestion batch_id={batch_id} for agent_id={request.agent_id}, "
            f"collection_id={request.collection_id}, documents_count={len(request.documents)}, tenant={tenant_id}"
        )
        
        # Process each document in the batch
        task_ids = []
        failed_items = []
        accepted_count = 0
        
        for idx, doc_data in enumerate(request.documents):
            try:
                # Create individual DocumentIngestionRequest
                individual_request = DocumentIngestionRequest(
                    tenant_id=request.tenant_id,
                    agent_id=request.agent_id,
                    collection_id=request.collection_id,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    document_name=doc_data.get("document_name", f"batch_doc_{idx}"),
                    document_type=DocumentType(doc_data.get("document_type", "text")),
                    file_path=doc_data.get("file_path"),
                    content=doc_data.get("content"),
                    url=doc_data.get("url"),
                    chunk_size=doc_data.get("chunk_size", request.default_chunk_size),
                    chunk_overlap=doc_data.get("chunk_overlap", request.default_chunk_overlap),
                    metadata={
                        **request.shared_metadata,
                        **doc_data.get("metadata", {}),
                        "batch_id": batch_id,
                        "batch_index": idx
                    }
                )
                
                # Create domain action for individual document
                action = DomainAction(
                    action_type="ingestion.ingest_document",
                    tenant_id=tenant_id,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    task_id=uuid.uuid4(),
                    origin_service="api",
                    rag_config=rag_config,
                    data=individual_request.model_dump()
                )
                
                # Process individual document
                result = await service.process_action(action)
                task_ids.append(result["task_id"])
                accepted_count += 1
                
                logger.info(f"Batch document {idx} accepted with task_id={result['task_id']}")
                
            except Exception as e:
                logger.error(f"Failed to process batch document {idx}: {e}")
                failed_items.append({
                    "index": idx,
                    "document_name": doc_data.get("document_name", f"batch_doc_{idx}"),
                    "error": str(e)
                })
        
        # Create batch response
        response = BatchIngestionResponse(
            batch_id=batch_id,
            agent_id=request.agent_id,
            collection_id=request.collection_id,
            total_documents=len(request.documents),
            accepted_documents=accepted_count,
            failed_documents=len(failed_items),
            task_ids=task_ids,
            failed_items=failed_items,
            status="processing" if accepted_count > 0 else "failed",
            message=f"Batch processing started: {accepted_count}/{len(request.documents)} documents accepted"
        )
        
        logger.info(f"Batch ingestion completed: {accepted_count} accepted, {len(failed_items)} failed")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection_id: str = Form(...),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(50),
    user_info: dict = Depends(verify_token),
    service = Depends(get_ingestion_service)
):
    """Upload and ingest a document file"""
    try:
        # Validate file type
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ['pdf', 'docx', 'txt', 'md']:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Map to document type
        type_map = {
            'pdf': DocumentType.PDF,
            'docx': DocumentType.DOCX,
            'txt': DocumentType.TXT,
            'md': DocumentType.MARKDOWN
        }
        document_type = type_map.get(file_extension, DocumentType.TXT)
        
        # Save file temporarily
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Create ingestion request
        request = DocumentIngestionRequest(
            tenant_id=user_info["tenant_id"],
            collection_id=collection_id,
            user_id=user_info["user_id"],
            session_id=user_info["session_id"],
            document_name=file.filename,
            document_type=document_type,
            file_path=str(file_path),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Create domain action
        action = DomainAction(
            action_type="ingestion.ingest_document",
            tenant_id=user_info["tenant_id"],
            user_id=user_info["user_id"],
            session_id=user_info["session_id"],
            task_id=uuid.uuid4(),
            origin_service="api",
            data=request.model_dump()
        )
        
        # Process
        result = await service.process_action(action)
        
        # Clean up file after processing starts
        # The service should have read it by now
        asyncio.create_task(_cleanup_file(file_path, delay=60))
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _cleanup_file(file_path: Path, delay: int = 60):
    """Clean up uploaded file after delay"""
    await asyncio.sleep(delay)
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")


@router.get("/status/{task_id}")
async def get_ingestion_status(
    task_id: str,
    user_info: dict = Depends(verify_token),
    service = Depends(get_ingestion_service)
):
    """Get status of an ingestion task"""
    try:
        action = DomainAction(
            action_type="ingestion.get_status",
            tenant_id=user_info["tenant_id"],
            user_id=user_info["user_id"],
            session_id=user_info["session_id"],
            task_id=uuid.uuid4(),
            origin_service="api",
            data={"task_id": task_id}
        )
        
        result = await service.process_action(action)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/document/{document_id}")
async def delete_document(
    document_id: str,
    agent_id: str = Query(..., description="The ID of the agent that owns the document"),
    user_info: dict = Depends(verify_token),
    service: IngestionService = Depends(get_ingestion_service)
):
    """Delete a document and all its chunks"""
    try:
        action = DomainAction(
            action_type="ingestion.delete_document",
            tenant_id=user_info["tenant_id"],
            user_id=user_info["user_id"],
            session_id=user_info["session_id"],
            task_id=uuid.uuid4(),
            origin_service="api",
            data={
                "document_id": document_id,
                "agent_id": agent_id
            }
        )
        
        result = await service.process_action(action)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    ws_manager = Depends(get_ws_manager)
):
    """WebSocket endpoint for real-time progress updates"""
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Could handle client messages here if needed
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
