# Ingestion Service - API Models Documentation

## Overview
Esta documentación describe los modelos de request y respuesta del **Ingestion Service** refactorizado para soportar arquitectura multi-agente con colección única en Qdrant.

## Arquitectura Unificada

### Jerarquía de Datos
```
tenant_id (Tenant)
  └── agent_id (Agent)
      └── collection_id (Virtual Collection)
          └── document_id (Document)
              └── chunk_id (Chunk)
```

### Colección Física Única
- **Colección**: `"documents"` (única colección física en Qdrant)
- **Separación Lógica**: Filtros virtuales por `tenant_id`, `agent_id`, `collection_id`
- **Beneficios**: Simplifica gestión, mejora rendimiento, asegura aislamiento multi-agente

---

## Models de Request

### 1. DocumentIngestionRequest
**Endpoint**: `POST /api/v1/ingestion/ingest`

```python
class DocumentIngestionRequest(BaseModel):
    # CONTEXTO REQUERIDO (Multi-Agent)
    tenant_id: str = Field(..., description="Tenant ID")
    agent_id: str = Field(..., description="Agent ID - REQUIRED for multi-agent isolation")
    collection_id: str = Field(..., description="Collection ID - REQUIRED for document organization")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Session ID")
    
    # DOCUMENTO
    document_name: str = Field(..., description="Document name")
    document_type: DocumentType = Field(..., description="Document type")
    file_path: Optional[str] = Field(None, description="Path to file")
    content: Optional[str] = Field(None, description="Direct text content")
    url: Optional[HttpUrl] = Field(None, description="URL to fetch content from")
    
    # CHUNKING
    chunk_size: int = Field(default=512, description="Size of chunks in tokens")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks")
    
    # METADATA
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

**Ejemplo**:
```json
{
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
```

### 2. BatchDocumentIngestionRequest
**Endpoint**: `POST /api/v1/ingestion/batch-ingest`

```python
class BatchDocumentIngestionRequest(BaseModel):
    # CONTEXTO COMPARTIDO (Multi-Agent)
    tenant_id: str = Field(..., description="Tenant ID")
    agent_id: str = Field(..., description="Agent ID - REQUIRED for multi-agent isolation")
    collection_id: str = Field(..., description="Collection ID - REQUIRED for document organization")
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Session ID")
    
    # DOCUMENTOS
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to ingest")
    
    # CONFIGURACIÓN COMPARTIDA
    default_chunk_size: int = Field(default=512, description="Default chunk size in tokens")
    default_chunk_overlap: int = Field(default=50, description="Default overlap between chunks")
    shared_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata applied to all documents")
```

**Ejemplo**:
```json
{
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
```

---

## Models de Response

### 1. IngestionResponse
**Endpoint**: `POST /api/v1/ingestion/ingest`

```python
class IngestionResponse(BaseModel):
    task_id: str = Field(..., description="Task ID for tracking")
    agent_id: str = Field(..., description="Agent ID")
    collection_id: str = Field(..., description="Collection ID")
    document_id: str = Field(..., description="Generated document ID")
    document_name: str = Field(..., description="Document name")
    status: str = Field(default="processing", description="Processing status")
    message: str = Field(..., description="Status message")
```

**Ejemplo**:
```json
{
  "task_id": "task-uuid-123",
  "agent_id": "agent-456",
  "collection_id": "kb-001",
  "document_id": "doc-uuid-789",
  "document_name": "PostgreSQL Guide",
  "status": "processing",
  "message": "Document queued for processing"
}
```

### 2. BatchIngestionResponse
**Endpoint**: `POST /api/v1/ingestion/batch-ingest`

```python
class BatchIngestionResponse(BaseModel):
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
```

**Ejemplo**:
```json
{
  "batch_id": "batch-uuid-456",
  "agent_id": "agent-456",
  "collection_id": "kb-001",
  "total_documents": 2,
  "accepted_documents": 2,
  "failed_documents": 0,
  "task_ids": ["task-uuid-123", "task-uuid-456"],
  "failed_items": [],
  "status": "processing",
  "message": "Batch processing started: 2/2 documents accepted"
}
```

---

## Modelos Internos

### 1. ChunkModel (Refactorizado)
```python
class ChunkModel(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = Field(..., description="Parent document ID")
    tenant_id: str = Field(..., description="Tenant ID")
    agent_id: str = Field(..., description="Agent ID that owns this chunk")
    collection_id: str = Field(..., description="Virtual collection ID")
    
    # CAMPO ESTANDARIZADO: text → content
    content: str = Field(..., description="Chunk text content")
    chunk_index: int = Field(..., description="Position in document")
    
    # ENRIQUECIMIENTOS
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    tags: List[str] = Field(default_factory=list, description="Generated tags")
    
    # EMBEDDING
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    
    # METADATA
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. DocumentType (Enum)
```python
class DocumentType(str, Enum):
    PDF = "pdf"
    TEXT = "text"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "md"
    JSON = "json"
    CSV = "csv"
```

---

## Validaciones Implementadas

### 1. Validación de Ownership
- **Agent → Tenant**: `agent_id` debe pertenecer al `tenant_id`
- **Collection → Agent**: `collection_id` debe pertenecer al `agent_id`
- **Formato UUID**: Validación de formato UUID para todos los IDs

### 2. Validación de Campos Requeridos
- `agent_id`: Requerido para aislamiento multi-agente
- `collection_id`: Requerido para organización de documentos
- `rag_config`: Requerido para configuración de embeddings

### 3. Validación de Documentos
- Al menos un documento requerido en batch upload
- Validación de tipos de documento soportados
- Validación de contenido o fuente de datos

---

## Headers Requeridos

### RAGConfig
```python
class RAGConfig(BaseModel):
    embedding_model: EmbeddingModel = Field(..., description="Embedding model")
    embedding_dimensions: int = Field(..., description="Embedding dimensions")
    encoding_format: str = Field(default="float", description="Encoding format")
    max_text_length: int = Field(default=8192, description="Maximum text length")
```

**Ejemplo Header**:
```json
{
  "embedding_model": "text-embedding-3-small",
  "embedding_dimensions": 1536,
  "encoding_format": "float",
  "max_text_length": 8192
}
```

---

## Endpoints Summary

| Endpoint | Method | Description | Request Model | Response Model |
|----------|--------|-------------|---------------|----------------|
| `/ingest` | POST | Single document ingestion | `DocumentIngestionRequest` | `IngestionResponse` |
| `/batch-ingest` | POST | Batch document ingestion | `BatchDocumentIngestionRequest` | `BatchIngestionResponse` |
| `/status/{task_id}` | GET | Check task status | - | `TaskStatus` |
| `/upload` | POST | File upload | `MultipartFile` | `UploadResponse` |

---

## Multi-Agent Isolation

### Filtros Virtuales en Qdrant
```python
# Búsqueda con filtros virtuales
search_filter = {
    "must": [
        {"key": "tenant_id", "match": {"value": tenant_id}},
        {"key": "agent_id", "match": {"value": agent_id}},
        {"key": "collection_id", "match": {"value": collection_id}}
    ]
}
```

### Beneficios de la Arquitectura Unificada
1. **Gestión Simplificada**: Una sola colección física
2. **Aislamiento Robusto**: Filtros virtuales por tenant/agent/collection
3. **Escalabilidad**: Manejo eficiente de múltiples agentes
4. **Compatibilidad**: Unificación entre ingestion y query services
5. **Mantenibilidad**: Configuración centralizada
