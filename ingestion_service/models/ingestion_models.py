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
    agent_id: str = Field(..., description="Agent ID that owns this document")
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
                "agent_id": "agent-456",
                "collection_id": "kb-001",
                "user_id": "user-789",
                "session_id": "session-abc",
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
    agent_id: str = Field(..., description="Agent ID that owns this chunk")
    collection_id: str = Field(..., description="Virtual collection ID")
    
    # CAMBIO CRÍTICO: text → content para compatibilidad con Query Service
    content: str = Field(..., description="Chunk text content")
    chunk_index: int = Field(..., description="Position in document")
    
    # Generated enrichments
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    tags: List[str] = Field(default_factory=list, description="Generated tags")
    
    # Embedding will be added after processing
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "chunk-uuid-123",
                "document_id": "doc-uuid-456",
                "tenant_id": "tenant-789",
                "agent_id": "agent-abc",
                "collection_id": "manuales-productos",
                "content": "Este es el contenido del chunk...",
                "chunk_index": 0,
                "keywords": ["manual", "producto"],
                "tags": ["documentacion", "tutorial"],
                "metadata": {"page": 1, "section": "intro"}
            }
        }


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
    agent_id: str
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


class BatchDocumentIngestionRequest(BaseModel):
    """Model for batch document ingestion request"""
    # Shared context for all documents
    tenant_id: str = Field(..., description="Tenant ID")
    agent_id: str = Field(..., description="Agent ID - REQUIRED for multi-agent isolation")
    collection_id: str = Field(..., description="Collection ID - REQUIRED for document organization")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Session ID")
    
    # List of documents to ingest
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to ingest")
    
    # Shared chunking parameters (can be overridden per document)
    default_chunk_size: int = Field(default=512, description="Default chunk size in tokens")
    default_chunk_overlap: int = Field(default=50, description="Default overlap between chunks")
    
    # Shared metadata
    shared_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata applied to all documents")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant-123",
                "agent_id": "agent-456", 
                "collection_id": "kb-001",
                "user_id": "user-789",
                "session_id": "session-abc",
                "documents": [
                    {
                        "document_name": "PostgreSQL Guide",
                        "document_type": "pdf",
                        "file_path": "/tmp/uploads/postgres-guide.pdf",
                        "metadata": {"category": "database", "version": "15"}
                    },
                    {
                        "document_name": "Redis Manual", 
                        "document_type": "pdf",
                        "file_path": "/tmp/uploads/redis-manual.pdf",
                        "metadata": {"category": "database", "version": "7"}
                    }
                ],
                "default_chunk_size": 512,
                "default_chunk_overlap": 50,
                "shared_metadata": {"project": "database-docs", "team": "backend"}
            }
        }


class BatchIngestionResponse(BaseModel):
    """Response model for batch ingestion"""
    batch_id: str = Field(..., description="Batch processing ID")
    agent_id: str = Field(..., description="Agent ID")
    collection_id: str = Field(..., description="Collection ID") 
    total_documents: int = Field(..., description="Total documents in batch")
    accepted_documents: int = Field(..., description="Documents accepted for processing")
    failed_documents: int = Field(..., description="Documents that failed validation")
    task_ids: List[str] = Field(..., description="Individual task IDs for each document")
    failed_items: List[Dict[str, Any]] = Field(default_factory=list, description="Failed document details")
    status: str = Field(default="processing", description="Batch status")
    message: str = Field(..., description="Status message")

