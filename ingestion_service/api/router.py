from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
import os
import aiofiles
from pathlib import Path

from common.models import DomainAction, RAGConfig
from ..models import DocumentIngestionRequest, DocumentType
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
        
        # Validate rag_config
        if not rag_config:
            raise HTTPException(
                status_code=400, 
                detail="rag_config is required for document ingestion"
            )
        
        logger.info(
            f"Ingesting document for agent_id={request.agent_id}, "
            f"document={request.document_name}, tenant={user_info['tenant_id']}"
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
    user_info: dict = Depends(verify_token),
    service = Depends(get_ingestion_service)
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
            data={"document_id": document_id}
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
