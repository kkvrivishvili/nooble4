"""
Endpoints para la ingesta de documentos.
"""

import logging
import uuid
import time
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, Query, Body
from pydantic import BaseModel, Field

from common.models import (
    TenantInfo, FileUploadResponse, BatchJobResponse, DocumentUploadMetadata,
    UrlIngestionRequest, TextIngestionRequest, BatchUrlsRequest
)
from common.errors import (
    handle_errors, DocumentProcessingError, ValidationError, ServiceError, ErrorCode
)
from common.context import with_context, Context
from common.auth import verify_tenant
from common.db.supabase import get_supabase_client
from common.db.tables import get_table_name
from common.config.tiers import get_tier_limits
from common.db.storage import upload_to_storage

# Importar configuración centralizada del servicio
from config.settings import get_settings, get_document_processor_config
from config.constants import (
    MAX_DOC_SIZE_MB,
    SUPPORTED_MIMETYPES
)

from services.queue import queue_document_processing_job
from services.chunking import validate_file

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

@router.post(
    "/upload",
    response_model=None,
    summary="Cargar documento",
    description="Carga un documento para procesamiento y generación de embeddings"
)
@with_context(tenant=True, collection=True)
@handle_errors(error_type="simple", log_traceback=False)
async def upload_document(
    file: UploadFile = File(...),
    tenant_info: TenantInfo = Depends(verify_tenant),
    collection_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    ctx: Context = None
):
    """
    Endpoint simplificado que solo sube a Storage y encola.
    
    Args:
        file: Archivo a procesar
        tenant_info: Información del tenant (inyectada por verify_tenant)
        collection_id: ID de la colección donde guardar el documento
        title: Título opcional del documento
        description: Descripción opcional del documento
        tags: Lista de etiquetas separadas por comas
        
    Returns:
        FileUploadResponse: Respuesta con información sobre el documento subido
        
    Raises:
        DocumentProcessingError: Si hay un error en el procesamiento
    """
    tenant_id = tenant_info.tenant_id
    
    # Incluir información para el contexto de error
    error_context = {
        "tenant_id": tenant_id,
        "collection_id": collection_id,
        "file_name": file.filename
    }
    
    try:
        # 0. Verificar límites del tier
        tier_limits = get_tier_limits(tenant_info.tier, tenant_id=tenant_id)
        max_docs = tier_limits.get("max_docs", 999999)
        
        # Contar documentos actuales del tenant
        supabase = get_supabase_client()
        doc_count_result = await supabase.table(get_table_name("documents")) \
            .select("count", count="exact") \
            .eq("tenant_id", tenant_id) \
            .execute()
            
        if doc_count_result.error:
            logger.error(f"Error contando documentos: {doc_count_result.error}", extra=error_context)
            raise ServiceError(
                message="Error al verificar límites de tier",
                error_code="TIER_LIMIT_CHECK_ERROR",
                status_code=500
            )
            
        current_docs = doc_count_result.count or 0
        
        # Verificar si excede el límite
        if current_docs >= max_docs:
            logger.warning(f"Límite de documentos excedido: {current_docs}/{max_docs}", 
                         extra=error_context)
            raise ValidationError(
                message=f"Límite de documentos excedido. El tier actual permite máximo {max_docs} documentos.",
                details={
                    "error_code": "TIER_LIMIT_EXCEEDED",
                    "limit_type": "max_docs",
                    "current": current_docs,
                    "max": max_docs,
                    "tier": tenant_info.tier
                }
            )
        
        # 1. Validar archivo
        file_info = await validate_file(file, ctx=ctx)
        
        # Procesar tags si están presentes
        tag_list = tags.split(",") if tags else []
        
        # Generar document_id único
        document_id = str(uuid.uuid4())
        
        # 2. Subir a Supabase Storage
        try:
            file_key = await upload_to_storage(
                tenant_id=tenant_id,
                collection_id=collection_id,
                file_content=await file.read(),
                file_name=file.filename
            )
        except Exception as storage_err:
            logger.error(f"Error al subir a Storage: {str(storage_err)}", extra=error_context)
            raise DocumentProcessingError(
                message="Error al almacenar el archivo",
                details=error_context
            )
        
        # 3. Encolar procesamiento
        try:
            job_id = await queue_document_processing_job(
                tenant_id=tenant_id,
                document_id=document_id,
                collection_id=collection_id,
                file_key=file_key,
                file_info={"type": file_info.mimetype, "size": file_info.file_size, "name": file_info.filename}
            )
        except Exception as queue_err:
            logger.error(f"Error al encolar trabajo: {str(queue_err)}", extra=error_context)
            raise DocumentProcessingError(
                message="Error al encolar el procesamiento",
                details={**error_context, "document_id": document_id}
            )
        
        return FileUploadResponse(
            success=True,
            message="Documento encolado para procesamiento",
            document_id=document_id,
            collection_id=collection_id,
            file_name=file.filename,
            job_id=job_id,
            status="pending"
        )
    except ValidationError as val_err:
        # Error de validación ya tiene el formato correcto
        logger.warning(f"Error de validación: {val_err.message}", extra=error_context)
        raise
    except DocumentProcessingError as doc_err:
        # Error de procesamiento ya tiene el formato correcto
        logger.error(f"Error de procesamiento: {doc_err.message}", extra=doc_err.context)
        raise
    except Exception as e:
        # Capturar errores inesperados con contexto mejorado
        error_context.update({
            "error_type": type(e).__name__,
            "operation": "upload_document",
            "traceback": traceback.format_exc()
        })
        logger.error(f"Error inesperado al cargar documento: {str(e)}", extra=error_context, exc_info=True)
        raise DocumentProcessingError(
            message=f"Error al cargar documento: {str(e)}",
            details=error_context
        )

@router.post(
    "/ingest-url",
    response_model=None,
    response_model_exclude_none=True,
    summary="Ingerir contenido de URL",
    description="Procesa y genera embeddings para el contenido de una URL"
)
@with_context(tenant=True, collection=True)
@handle_errors(error_type="simple", log_traceback=False)
async def ingest_url(
    request: UrlIngestionRequest,
    tenant_info: TenantInfo = Depends(verify_tenant),
    ctx: Context = None
):
    """
    Procesa y genera embeddings para el contenido de una URL.
    
    Args:
        request: Datos de la URL a procesar
        tenant_info: Información del tenant
        
    Returns:
        FileUploadResponse: Resultado de la operación
    """
    tenant_id = tenant_info.tenant_id
    
    try:
        # Validar URL
        if not request.url.startswith(("http://", "https://")):
            raise ValidationError(
                message="URL inválida, debe comenzar con http:// o https://",
                details={"url": request.url}
            )
        
        # Generar ID único para el documento
        document_id = str(uuid.uuid4())
        
        # Crear metadatos para el documento
        document_metadata = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "collection_id": request.collection_id,
            "title": request.title or "URL Content",
            "description": request.description,
            "file_name": request.url,
            "file_type": "url",
            "tags": request.tags,
            "status": "pending",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        # Guardar metadatos en Supabase
        supabase = get_supabase_client()
        result = await supabase.table(get_table_name("documents")).insert(document_metadata).execute()
        
        if result.error:
            raise DocumentProcessingError(
                message=f"Error guardando metadatos del documento URL: {result.error}",
                details={"tenant_id": tenant_id, "url": request.url}
            )
        
        # Encolamos el trabajo de procesamiento
        job_id = await queue_document_processing_job(
            tenant_id=tenant_id,
            document_id=document_id,
            collection_id=request.collection_id,
            url=request.url,
            file_info={"type": "url", "size": 0}
        )
        
        return FileUploadResponse(
            success=True,
            message="URL encolada para procesamiento",
            document_id=document_id,
            collection_id=request.collection_id,
            file_name=request.url,
            job_id=job_id,
            status="pending"
        )
        
    except Exception as e:
        logger.error(f"Error al procesar URL: {str(e)}")
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            message=f"Error al procesar URL: {str(e)}",
            details={"url": request.url}
        )

class TextIngestionRequest(BaseModel):
    text: str
    collection_id: str
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None

@router.post(
    "/ingest-text",
    response_model=None,
    response_model_exclude_none=True,
    summary="Ingerir texto plano",
    description="Procesa y genera embeddings para texto plano"
)
@with_context(tenant=True, collection=True)
@handle_errors(error_type="simple", log_traceback=False)
async def ingest_text(
    request: TextIngestionRequest,
    tenant_info: TenantInfo = Depends(verify_tenant),
    ctx: Context = None
):
    """
    Procesa y genera embeddings para texto plano.
    
    Args:
        request: Datos del texto a procesar
        tenant_info: Información del tenant
        
    Returns:
        FileUploadResponse: Resultado de la operación
    """
    tenant_id = tenant_info.tenant_id
    
    try:
        # Validar texto
        if not request.text.strip():
            raise ValidationError(
                message="El texto no puede estar vacío",
                details={"text_length": 0}
            )
        
        # Generar ID único para el documento
        document_id = str(uuid.uuid4())
        
        # Crear metadatos para el documento
        document_metadata = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "collection_id": request.collection_id,
            "title": request.title,
            "description": request.description,
            "file_name": "custom_text.txt",
            "file_type": "text",
            "tags": request.tags,
            "status": "pending",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        # Guardar metadatos en Supabase
        supabase = get_supabase_client()
        result = await supabase.table(get_table_name("documents")).insert(document_metadata).execute()
        
        if result.error:
            raise DocumentProcessingError(
                message=f"Error guardando metadatos del documento de texto: {result.error}",
                details={"tenant_id": tenant_id}
            )
        
        # Encolamos el trabajo de procesamiento
        job_id = await queue_document_processing_job(
            tenant_id=tenant_id,
            document_id=document_id,
            collection_id=request.collection_id,
            text_content=request.text,
            file_info={"type": "text", "size": len(request.text)}
        )
        
        return FileUploadResponse(
            success=True,
            message="Texto encolado para procesamiento",
            document_id=document_id,
            collection_id=request.collection_id,
            file_name="custom_text.txt",
            job_id=job_id,
            status="pending"
        )
        
    except Exception as e:
        logger.error(f"Error al procesar texto: {str(e)}")
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            message=f"Error al procesar texto: {str(e)}",
            details={"text_length": len(request.text)}
        )

class BatchUrlsRequest(BaseModel):
    urls: List[str]
    collection_id: str
    title_prefix: Optional[str] = None
    tags: Optional[List[str]] = None

@router.post(
    "/batch-urls",
    response_model=None,
    response_model_exclude_none=True,
    summary="Procesar lote de URLs",
    description="Procesa un lote de URLs en segundo plano"
)
@with_context(tenant=True, collection=True)
@handle_errors(error_type="simple", log_traceback=False)
async def batch_process_urls(
    request: BatchUrlsRequest,
    tenant_info: TenantInfo = Depends(verify_tenant),
    ctx: Context = None
):
    """
    Procesa un lote de URLs en segundo plano.
    
    Args:
        request: Lista de URLs y metadatos
        tenant_info: Información del tenant
        
    Returns:
        BatchJobResponse: ID del trabajo por lotes y estadísticas
    """
    tenant_id = tenant_info.tenant_id
    
    try:
        # Validar URLs
        urls = [url for url in request.urls if url.startswith(("http://", "https://"))]
        if len(urls) == 0:
            raise ValidationError(
                message="No se proporcionaron URLs válidas",
                details={"urls_count": len(request.urls)}
            )
        
        # Generar ID único para el trabajo por lotes
        batch_id = str(uuid.uuid4())
        
        # Crear trabajos individuales para cada URL
        job_ids = []
        for i, url in enumerate(urls):
            # Título generado automáticamente si no se proporciona
            title = f"{request.title_prefix or 'URL'} {i+1}" if not request.title_prefix else f"{request.title_prefix} {i+1}"
            
            # Generar ID único para el documento
            document_id = str(uuid.uuid4())
            
            # Crear metadatos para el documento
            document_metadata = {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "collection_id": request.collection_id,
                "title": title,
                "description": f"Procesado en lote {batch_id}",
                "file_name": url,
                "file_type": "url",
                "tags": request.tags,
                "batch_id": batch_id,
                "status": "pending",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            
            # Guardar metadatos en Supabase
            supabase = get_supabase_client()
            result = await supabase.table(get_table_name("documents")).insert(document_metadata).execute()
            
            if result.error:
                logger.error(f"Error guardando metadatos para URL {url}: {result.error}")
                continue
            
            # Encolar trabajo de procesamiento
            job_id = await queue_document_processing_job(
                tenant_id=tenant_id,
                document_id=document_id,
                collection_id=request.collection_id,
                url=url,
                file_info={"type": "url", "size": 0},
                batch_id=batch_id
            )
            
            job_ids.append(job_id)
        
        return BatchJobResponse(
            success=True,
            message=f"Lote de {len(job_ids)} URLs encoladas para procesamiento",
            batch_id=batch_id,
            job_count=len(job_ids),
            failed_count=len(urls) - len(job_ids),
            status="processing"
        )
        
    except Exception as e:
        logger.error(f"Error al procesar lote de URLs: {str(e)}")
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            message=f"Error al procesar lote de URLs: {str(e)}",
            details={"urls_count": len(request.urls) if hasattr(request, "urls") else 0}
        )