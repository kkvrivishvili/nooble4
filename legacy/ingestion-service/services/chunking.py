"""Módulo centralizado para procesamiento de documentos, extracción de texto y chunking.

Este módulo unifica todas las operaciones de procesamiento documental:
- Extracción de texto con LlamaIndex desde diferentes formatos
- Validación y análisis de archivos
- Chunking inteligente de texto usando LlamaIndex
- Procesamiento de archivos desde almacenamiento

Implementa patrones de caché optimizados para reducir procesamiento redundante.
"""

import logging
import os
import tempfile
import mimetypes
import hashlib
import time
import tiktoken
from typing import List, Dict, Any, Optional, Union, BinaryIO, Tuple
from pathlib import Path

from fastapi import UploadFile

# Herramientas de LlamaIndex para procesamiento documental
from llama_index.core import (
    Document, VectorStoreIndex, Settings, 
    ServiceContext, StorageContext, SimpleDirectoryReader
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file import (
    PDFReader, DocxReader, CSVReader, 
    PandasExcelReader, MarkdownReader, ImageReader
)
# BeautifulSoup para procesamiento HTML personalizado
from bs4 import BeautifulSoup

# Componentes internos del sistema
from common.errors import ServiceError, ErrorCode, DocumentProcessingError, ValidationError, handle_errors
from common.config.tiers import get_tier_limits
from common.context import with_context, Context
from common.tracking import track_token_usage, TOKEN_TYPE_LLM, OPERATION_GENERATION, estimate_prompt_tokens
from common.cache import (
    get_with_cache_aside,
    invalidate_document_update,
    generate_resource_id_hash,
    CacheManager,
    standardize_llama_metadata
)

# Importar configuración centralizada del servicio
from config.settings import get_settings
from config.constants import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MAX_WORKERS,
    MAX_DOC_SIZE_MB,
    SUPPORTED_MIMETYPES,
    EXTRACTION_CONFIG,
    TIMEOUTS
)


logger = logging.getLogger(__name__)

# Implementación personalizada de HTMLReader
class CustomHTMLReader:
    """Lector personalizado para contenido HTML usando BeautifulSoup."""
    
    def load_data(self, file_path=None, html_str=None):
        """Carga y procesa contenido HTML ya sea desde un archivo o desde una cadena."""
        if file_path is None and html_str is None:
            raise ValueError("Debe proporcionar file_path o html_str")
        
        content = ""
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = html_str
        
        # Procesar con BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Eliminar scripts, estilos y otros elementos no deseados
        for element in soup(["script", "style", "header", "footer", "nav"]):
            element.decompose()
        
        # Extraer texto limpio
        text = soup.get_text(separator=" ", strip=True)
        
        # Crear documento
        return [Document(text=text)]

# Mapa de tipos MIME a lectores de LlamaIndex
LLAMA_READERS = {
    'application/pdf': PDFReader(),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocxReader(),
    'text/csv': CSVReader(),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': PandasExcelReader(),
    'application/vnd.ms-excel': PandasExcelReader(),
    'text/markdown': MarkdownReader(),
    'text/html': CustomHTMLReader(),
    'text/plain': SimpleDirectoryReader,
    'image/jpeg': ImageReader(),
    'image/png': ImageReader(),
    'image/gif': ImageReader(),
}

# Extensiones para detectar tipos MIME
MIME_EXTENSIONS = {
    '.md': 'text/markdown',
    '.txt': 'text/plain',
    '.csv': 'text/csv',
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
}

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def split_text_into_chunks(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    metadata: Dict[str, Any] = None,
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Divide un texto en chunks usando LlamaIndex.
    
    Args:
        text: Texto completo a dividir
        chunk_size: Tamaño máximo de cada chunk en caracteres
        chunk_overlap: Número de caracteres que se solapan entre chunks
        metadata: Metadatos a incluir en cada chunk
        ctx: Contexto de la operación
        
    Returns:
        List[Dict[str, Any]]: Lista de chunks con metadatos
    """
    # Validaciones básicas
    if not text or not isinstance(text, str):
        raise DocumentProcessingError("El texto a dividir no es válido")
    
    if len(text) == 0:
        logger.warning("Se recibió un texto vacío para dividir")
        return []
    
    # Generar un document_id si no está en los metadatos
    metadata = metadata or {}
    document_id = metadata.get("document_id", f"doc_{hash(text)[:8]}")
    
    # Usar nuestra implementación directamente
    return await split_text_with_llama_index(
        text=text,
        document_id=document_id,
        metadata=metadata,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        ctx=ctx
    )

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def split_document_intelligently(
    text: str,
    document_id: str,
    metadata: Dict[str, Any],
    chunk_size: int = None,
    chunk_overlap: int = None,
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Divide un documento de forma inteligente con LlamaIndex.
    
    Args:
        text: Texto del documento
        document_id: ID del documento
        metadata: Metadatos del documento
        chunk_size: Tamaño de fragmento
        chunk_overlap: Solapamiento entre fragmentos
        ctx: Contexto de la operación
        
    Returns:
        List[Dict[str, Any]]: Lista de fragmentos con metadatos
    """
    # Asegurarse de que metadata tenga document_id
    doc_metadata = dict(metadata or {})
    doc_metadata["document_id"] = document_id
    
    try:
        # Verificar si el tenant tiene acceso a RAG avanzado según su tier
        tier = "free"  # Valor por defecto
        if ctx and hasattr(ctx, 'tenant_info') and ctx.tenant_info:
            tier = ctx.tenant_info.tier
            
        # Obtener los límites del tier para verificar si tiene RAG avanzado
        tenant_id = metadata.get("tenant_id")
        tier_limits = get_tier_limits(tier, tenant_id=tenant_id)
        has_advanced_rag = tier_limits.get("has_advanced_rag", False)
        
        logger.info(f"Tenant tier: {tier}, advanced RAG access: {has_advanced_rag}")
        
        # Uso directo de la función centralizada
        return await split_text_with_llama_index(
            text=text,
            document_id=document_id,
            metadata=doc_metadata,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            ctx=ctx
        )
    except Exception as e:
        logger.error(f"Error dividiendo documento {document_id}: {str(e)}")
        raise ServiceError(
            error_code=ErrorCode.PROCESSING_ERROR, 
            message=f"Error dividiendo documento con LlamaIndex: {str(e)}",
            details={"document_id": document_id}
        )

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def split_text_with_llama_index(
    text: str,
    document_id: str,
    metadata: Dict[str, Any],
    chunk_size: int = None,
    chunk_overlap: int = None,
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Divide un texto en chunks utilizando LlamaIndex para un chunking inteligente.
    
    Args:
        text: Texto a dividir
        document_id: ID del documento
        metadata: Metadatos a incluir en cada chunk
        chunk_size: Tamaño de cada chunk
        chunk_overlap: Solapamiento entre chunks
        ctx: Contexto de la operación
        
    Returns:
        List[Dict[str, Any]]: Lista de chunks con texto y metadata
    """
    # Obtener tenant_id del metadata o contexto
    tenant_id = metadata.get("tenant_id")
    if not tenant_id and ctx and hasattr(ctx, "tenant_id"):
        tenant_id = ctx.tenant_id
    
    # Obtener tier para determinar los parámetros de chunking
    tier = "free"  # Valor por defecto
    if ctx and hasattr(ctx, 'tenant_info') and ctx.tenant_info:
        tier = ctx.tenant_info.tier
    
    # Obtener límites del tier
    tier_limits = get_tier_limits(tier, tenant_id=tenant_id)
    
    # Determinar tamaño y solapamiento de chunks según tier
    default_chunk_size = tier_limits.get("default_chunk_size", 1024)
    default_chunk_overlap = tier_limits.get("default_chunk_overlap", 200)
    
    # Usar valores proporcionados o predeterminados
    chunk_size = chunk_size or default_chunk_size
    chunk_overlap = chunk_overlap or default_chunk_overlap
    
    try:
        # Normalizar el texto para evitar problemas
        text = text.strip()
        if not text:
            logger.warning(f"Texto vacío para documento {document_id}")
            return []
        
        # Crear un nodo Document para LlamaIndex
        document = Document(text=text, metadata=metadata)
        
        # Usar SentenceSplitter para chunks de tamaño adecuado
        splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            paragraph_separator="\n\n",  # Respeta párrafos
            secondary_chunking_regex="[^,.;:\n]+[,.;:\n]",  # Divide por frases
        )
        
        # Calcular tokens para tracking antes del chunking (solo si se usara LLM, pero podemos trackear el texto de entrada)
        # Esto permitirá entender el costo de procesamiento y chunking del documento
        text_tokens = await estimate_prompt_tokens(text)
        
        # Registrar uso de tokens para el proceso de chunking
        doc_hash = hashlib.md5(text[:200].encode()).hexdigest()[:10] # Usar parte del texto para el hash
        collection_id = metadata.get("collection_id")
        idempotency_key = f"chunk:{tenant_id}:{document_id}:{doc_hash}:{int(time.time())}"
        
        await track_token_usage(
            tenant_id=tenant_id,
            tokens=text_tokens,
            model="text-chunking-processor",  # Nombre estándar para el procesador de chunking
            token_type=TOKEN_TYPE_LLM,  # Usar constante estandarizada
            operation=OPERATION_GENERATION,  # Esta operación es más cercana a generación
            collection_id=collection_id,
            idempotency_key=idempotency_key,  # Prevenir doble conteo
            metadata={
                "document_id": document_id,
                "operation": "chunking",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "text_length": len(text),
                "tier": tier
            }
        )
        
        # Dividir documento
        nodes = splitter.get_nodes_from_documents([document])
        
        # Primero, estandarizar los metadatos base del documento
        # Importamos del módulo completo para facilitar futuras refactorizaciones
        from common.cache import standardize_llama_metadata
        
        # Obtener tenant_id de los metadatos o contexto
        tenant_id = metadata.get("tenant_id")
        if not tenant_id and ctx and hasattr(ctx, "tenant_id"):
            tenant_id = ctx.tenant_id
        
        collection_id = metadata.get("collection_id")
            
        # Convertir nodos a formato unificado
        chunks = []
        for i, node in enumerate(nodes):
            node_text = node.text.strip()
            if not node_text:
                continue
                
            # Generar chunk_id consistente (formato estandarizado: document_id_índice)
            chunk_id = f"{document_id}_{i}"
            
            # CRÍTICO: Estandarizar metadatos para garantizar consistencia en caché y tracking
            # Esta estandarización asegura campos obligatorios como tenant_id y document_id
            # y mantiene el formato consistente en todos los servicios (embedding, query, etc.)
            try:
                node_metadata = standardize_llama_metadata(
                    metadata=dict(node.metadata),
                    tenant_id=tenant_id,  # Campo crítico para multitenancy
                    document_id=document_id,  # Obligatorio para chunks, permite trazabilidad
                    chunk_id=chunk_id,  # Identificador único para este fragmento
                    collection_id=collection_id,  # Necesario para caché jerárquica
                    ctx=ctx  # Contexto para valores por defecto si faltan campos
                )
            except ValueError as ve:
                # Errores específicos de metadatos (campos faltantes o formato incorrecto)
                logger.error(f"Error en estandarización de metadatos: {str(ve)}",
                           extra={"document_id": document_id, "chunk_id": chunk_id})
                # Reintentar con metadatos básicos para evitar fallo total
                node_metadata = standardize_llama_metadata(
                    metadata={},  # Metadatos mínimos
                    tenant_id=tenant_id,
                    document_id=document_id,
                    chunk_id=chunk_id
                )
            except Exception as e:
                # Otros errores inesperados
                logger.error(f"Error inesperado en estandarización: {str(e)}",
                           extra={"document_id": document_id})
                raise DocumentProcessingError(f"Error en metadatos: {str(e)}")
                
            # Añadir campos adicionales específicos que no maneja la función estándar
            # Estos campos son específicos de la ingestion y no forman parte del estándar común
            node_metadata["chunk_index"] = i
            
            # Añadir el chunk con metadatos estandarizados
            chunks.append({
                "id": node_metadata["chunk_id"],
                "text": node_text,
                "metadata": node_metadata
            })
        
        logger.info(f"Documento {document_id} dividido en {len(chunks)} chunks")
        
        # Registrar métricas adicionales sobre el resultado del chunking
        try:
            # Solo actualizamos los metadatos del tracking ya realizado
            chunk_count = len(chunks)
            chunk_sizes = [len(chunk["text"]) for chunk in chunks]
            avg_chunk_size = sum(chunk_sizes) / chunk_count if chunk_count else 0
            
            logger.debug(f"Estadísticas de chunking: {chunk_count} chunks, tamaño promedio: {avg_chunk_size:.2f} caracteres")
        except Exception as metrics_err:
            logger.warning(f"Error registrando métricas de chunking: {str(metrics_err)}")
        
        return chunks
        
    except Exception as e:
        logger.error(f"Error dividiendo texto con LlamaIndex: {str(e)}")
        raise DocumentProcessingError(
            f"Error dividiendo texto con LlamaIndex: {str(e)}",
            details={
                "document_id": document_id,
                "error": str(e)
            }
        )

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def validate_file(
    file: UploadFile,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Valida un archivo subido para determinar si puede ser procesado.
    
    Args:
        file: Archivo subido mediante FastAPI
        ctx: Contexto de la operación
        
    Returns:
        Dict[str, Any]: Información del archivo validado incluyendo mimetype, tamaño, etc.
        
    Raises:
        ValidationError: Si el archivo no es válido por alguna razón
    """
    if not file:
        raise ValidationError("No se ha proporcionado ningún archivo")
    
    # Obtener información básica
    filename = file.filename
    file_ext = os.path.splitext(filename)[1].lower() if filename else ""
    
    # Verificar nombre de archivo
    if not filename or len(filename.strip()) == 0:
        raise ValidationError("Nombre de archivo no válido")
    
    # Determinar tipo MIME
    content_type = file.content_type
    
    # Si el content-type no es proporcionado o no es confiable, inferir desde la extensión
    if not content_type or content_type == "application/octet-stream":
        content_type = MIME_EXTENSIONS.get(file_ext, "application/octet-stream")
    
    # Verificar si el tipo de archivo es soportado
    if content_type not in LLAMA_READERS and file_ext not in MIME_EXTENSIONS:
        raise ValidationError(
            f"Tipo de archivo no soportado: {content_type}",
            details={
                "content_type": content_type,
                "filename": filename,
                "extension": file_ext
            }
        )
    
    # Leer y verificar el tamaño del archivo
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        # Rebobinar el archivo para uso futuro
        await file.seek(0)
        
        # Verificar tamaño máximo (10MB por defecto)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise ValidationError(
                f"El archivo excede el tamaño máximo permitido de {max_size/1024/1024:.1f}MB",
                details={"size": file_size, "max_size": max_size}
            )
        
        # Calcular hash para identificación única
        file_hash = hashlib.md5(file_content).hexdigest()
        
        # Devolver información del archivo validado
        return {
            "filename": filename,
            "content_type": content_type,
            "size": file_size,
            "hash": file_hash,
            "extension": file_ext
        }
        
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        
        logger.error(f"Error validando archivo: {str(e)}")
        raise ValidationError(
            f"Error validando archivo: {str(e)}",
            details={"filename": filename, "error": str(e)}
        )

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def extract_text_from_file(
    file_path: str,
    mimetype: str,
    metadata: Dict[str, Any] = None,
    ctx: Context = None
) -> str:
    """
    Extrae texto de un archivo usando los readers apropiados de LlamaIndex.
    
    Args:
        file_path: Ruta al archivo en el sistema
        mimetype: Tipo MIME del archivo
        metadata: Metadatos adicionales
        ctx: Contexto de la operación
        
    Returns:
        str: Texto extraído del archivo
    """
    if not os.path.exists(file_path):
        raise DocumentProcessingError(f"Archivo no encontrado: {file_path}")
    
    # Verificar extensión si el mimetype no es claro
    file_ext = os.path.splitext(file_path)[1].lower()
    if mimetype == "application/octet-stream" and file_ext in MIME_EXTENSIONS:
        mimetype = MIME_EXTENSIONS[file_ext]
    
    # Obtener el lector adecuado
    reader = LLAMA_READERS.get(mimetype)
    if not reader:
        raise DocumentProcessingError(f"No hay un lector disponible para {mimetype}")
    
    try:
        # Extraer documentos
        documents = []
        
        # SimpleDirectoryReader requiere un tratamiento especial
        if mimetype == "text/plain":
            # Leer el contenido directamente para archivos de texto
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
                documents = [Document(text=text, metadata=metadata or {})]
        else:
            # Usar el lector específico
            documents = reader.load_data(file_path)
        
        # Verificar resultados
        if not documents:
            logger.warning(f"No se extrajeron documentos del archivo {file_path}")
            return ""
        
        # Concatenar texto de todos los documentos
        full_text = "\n\n".join(doc.text for doc in documents if doc.text)
        
        logger.info(f"Texto extraído correctamente de {os.path.basename(file_path)}: {len(full_text)} caracteres")
        return full_text
        
    except Exception as e:
        logger.error(f"Error extrayendo texto de {file_path}: {str(e)}")
        raise DocumentProcessingError(
            f"Error procesando archivo {os.path.basename(file_path)}: {str(e)}",
            details={"file": file_path, "mimetype": mimetype, "error": str(e)}
        )

@with_context(tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def process_file_from_storage(
    tenant_id: str,
    collection_id: str,
    file_key: str,
    ctx: Context = None
) -> str:
    """
    Procesa un archivo desde Storage usando el patrón Cache-Aside.
    
    Args:
        tenant_id: ID del tenant
        collection_id: ID de la colección
        file_key: Clave del archivo en Storage
        ctx: Contexto de la operación
        
    Returns:
        str: Texto procesado del documento
    """
    # Calcular hash del archivo una sola vez y reutilizarlo
    file_hash = generate_resource_id_hash(file_key)
    
    # Función para obtener el texto desde la base de datos (inexistente en este caso)
    async def fetch_from_db(resource_id, tenant_id, ctx=None):
        # En este caso no hay base de datos para textos extraídos
        return None
        
    # Función para generar el texto del archivo si no está en caché
    async def process_and_extract():
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                start_time = time.time()
                # Descargar archivo desde Storage
                file_path, file_metadata = await download_file_from_storage(
                    tenant_id=tenant_id,
                    file_key=file_key,
                    destination=temp_dir,
                    ctx=ctx
                )
                
                # Verificar descarga exitosa
                if not file_path or not os.path.exists(file_path):
                    raise ServiceError(
                        message=f"No se pudo descargar el archivo {file_key}",
                        error_code=ErrorCode.STORAGE_ERROR
                    )
                
                # Preparar metadatos - usar directamente el hash calculado previamente
                document_id = file_metadata.get("document_id") or file_hash[:10]
                metadata = {
                    "tenant_id": tenant_id,
                    "collection_id": collection_id,
                    "document_id": document_id,
                    "file_name": file_metadata.get("filename", ""),
                    "file_key": file_key,
                    "file_hash": file_hash  # Incluir el hash para evitar recalcularlo
                }
                
                # Extraer texto usando LlamaIndex
                mimetype = file_metadata.get("content_type", "application/octet-stream")
                extracted_text = await extract_text_from_file(
                    file_path=file_path,
                    mimetype=mimetype,
                    metadata=metadata,
                    ctx=ctx
                )
                
                # Registrar tiempo de procesamiento
                processing_time = time.time() - start_time
                logger.info(
                    f"Texto extraído de {file_metadata.get('filename', 'documento')}: "
                    f"{len(extracted_text)} caracteres en {processing_time:.2f}s"
                )
                
                return extracted_text
                
            except Exception as e:
                logger.error(f"Error procesando archivo {file_key}: {str(e)}")
                if isinstance(e, ServiceError):
                    raise
                
                raise ServiceError(
                    message=f"Error procesando documento: {str(e)}",
                    error_code=ErrorCode.PROCESSING_ERROR,
                    details={"file_key": file_key, "error": str(e)}
                )
    
    # Usar el patrón Cache-Aside centralizado
    
    # Obtener texto extraído con caché usando la implementación centralizada
    extracted_text, metrics = await get_with_cache_aside(
        data_type="extracted_text",
        resource_id=file_hash,
        tenant_id=tenant_id,
        fetch_from_db_func=fetch_from_db,
        generate_func=process_and_extract,
        collection_id=collection_id,  # Mejorar especificidad de caché
        ctx=ctx
        # TTL se determina automáticamente según el tipo de dato
    )
    
    # Registrar métricas si hay contexto
    if ctx:
        ctx.add_metric("text_extraction_cache", metrics)
        
    return extracted_text