from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
import uuid


class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    MARKDOWN = "markdown"
    URL = "url"


class DocumentIngestionRequest(BaseModel):
    """Request model for document ingestion"""
    tenant_id: str = Field(..., description="Tenant ID for multitenancy")
    collection_id: str = Field(..., description="Virtual collection ID within tenant")
    user_id: str = Field(..., description="User initiating the ingestion")
    session_id: str = Field(..., description="Session ID for tracking")
    
    document_name: str = Field(..., description="Name of the document")
    document_type: DocumentType = Field(..., description="Type of document")
    
    # Either file_path, content, or url must be provided
    file_path: Optional[str] = Field(None, description="Path to uploaded file")
    content: Optional[str] = Field(None, description="Direct text content")
    url: Optional[HttpUrl] = Field(None, description="URL to fetch content from")
    
    # Chunking parameters
    chunk_size: int = Field(default=512, description="Size of chunks in tokens")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-123",
                "collection_id": "kb-001",
                "user_id": "user-456",
                "session_id": "session-789",
                "document_name": "PostgreSQL Guide",
                "document_type": "pdf",
                "file_path": "/tmp/uploads/postgres-guide.pdf",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "metadata": {"category": "database", "version": "15"}
            }
        }


class ChunkModel(BaseModel):
    """Model for document chunks"""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = Field(..., description="Parent document ID")
    tenant_id: str = Field(..., description="Tenant ID")
    collection_id: str = Field(..., description="Virtual collection ID")
    
    text: str = Field(..., description="Chunk text content")
    chunk_index: int = Field(..., description="Position in document")
    
    # Generated enrichments
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    tags: List[str] = Field(default_factory=list, description="Generated tags")
    
    # Embedding will be added after processing
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingProgress(BaseModel):
    """Progress update for WebSocket notifications"""
    task_id: str
    status: IngestionStatus
    current_step: str
    progress_percentage: float
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class IngestionTask(BaseModel):
    """Internal model for tracking ingestion tasks"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: str
    session_id: str
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    status: IngestionStatus = Field(default=IngestionStatus.PENDING)
    request: DocumentIngestionRequest
    
    total_chunks: int = Field(default=0)
    processed_chunks: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
