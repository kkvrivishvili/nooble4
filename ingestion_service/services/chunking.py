"""
Servicio de fragmentación (chunking) de documentos con LlamaIndex.

Este módulo proporciona funcionalidades avanzadas para:
- Extracción de texto desde diferentes formatos de archivo
- Fragmentación inteligente usando LlamaIndex
- Validación y análisis de documentos
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

# LlamaIndex para procesamiento documental
from llama_index.core import (
    Document, VectorStoreIndex, Settings, 
    ServiceContext, StorageContext, SimpleDirectoryReader
)
from llama_index.core.node_parser import SentenceSplitter, NodeParser
from llama_index.readers.file import (
    PDFReader, DocxReader, CSVReader, 
    PandasExcelReader, MarkdownReader, ImageReader
)
# BeautifulSoup para procesamiento HTML personalizado
from bs4 import BeautifulSoup

from common.context import with_context, Context
from common.errors import ValidationError, DocumentProcessingError
from ingestion_service.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CustomHTMLReader:
    """Lector personalizado para contenido HTML usando BeautifulSoup."""
    
    def load_data(self, file_path=None, html_str=None):
        """Carga y procesa contenido HTML ya sea desde un archivo o desde una cadena.
        
        Args:
            file_path: Ruta al archivo HTML (opcional)
            html_str: Contenido HTML como string (opcional)
            
        Returns:
            List[Document]: Lista de documentos procesados
        """
        if file_path is None and html_str is None:
            raise ValueError("Debe proporcionar file_path o html_str")
        
        content = html_str
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # Procesar con BeautifulSoup para extraer el texto relevante
        soup = BeautifulSoup(content, 'html.parser')
        
        # Eliminar tags no deseados que no aportan contenido significativo
        for tag in soup(['style', 'script', 'head', 'header', 'footer', 'nav']):
            tag.decompose()
        
        # Extraer texto
        text = soup.get_text(separator='\n', strip=True)
        
        # Crear documento LlamaIndex
        metadata = {"source": file_path} if file_path else {"source": "html_string"}
        return [Document(text=text, metadata=metadata)]


# Mapa de tipos MIME a lectores de LlamaIndex
LLAMA_READERS = {
    'application/pdf': PDFReader(),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': DocxReader(),
    'application/vnd.ms-excel': PandasExcelReader(),
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': PandasExcelReader(),
    'text/csv': CSVReader(),
    'text/markdown': MarkdownReader(),
    'text/html': CustomHTMLReader(),
    'image/jpeg': ImageReader(),
    'image/png': ImageReader(),
    'image/gif': ImageReader(),
    'image/webp': ImageReader(),
}

# Extensiones de texto plano que podemos manejar directamente
TEXT_EXTENSIONS = {
    '.txt': 'text/plain',
    '.md': 'text/markdown',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.csv': 'text/csv',
    '.json': 'application/json',
    '.py': 'text/x-python',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.xml': 'application/xml',
}


class ChunkingService:
    """Servicio para procesamiento y fragmentación de documentos."""
    
    def __init__(self):
        """Inicializa el servicio de chunking."""
        # Registramos tipos MIME adicionales que no estén en el sistema
        for ext, mime in TEXT_EXTENSIONS.items():
            mimetypes.add_type(mime, ext)
    
    @with_context
    async def split_text_into_chunks(
        self,
        text: str,
        chunk_size: int = None,
        chunk_overlap: int = None,
        metadata: Dict[str, Any] = None,
        ctx: Context = None
    ) -> List[Dict[str, Any]]:
        """Divide un texto en chunks usando LlamaIndex.
        
        Args:
            text: Texto completo a dividir
            chunk_size: Tamaño máximo de cada chunk en caracteres
            chunk_overlap: Número de caracteres que se solapan entre chunks
            metadata: Metadatos a incluir en cada chunk
            ctx: Contexto de la operación
            
        Returns:
            List[Dict[str, Any]]: Lista de chunks con metadatos
        """
        if not text:
            return []
        
        # Configurar tamaños por defecto si no se especifican
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        metadata = metadata or {}
        
        logger.info(
            f"Fragmentando texto de {len(text)} caracteres con chunk_size={chunk_size}, "
            f"chunk_overlap={chunk_overlap}"
        )
        
        try:
            # Crear el parser de LlamaIndex
            splitter = SentenceSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                paragraph_separator="\n\n",
                secondary_chunking_regex=r"\n",
                tokenizer=tiktoken.encoding_for_model("gpt-4").encode
            )
            
            # Crear documento LlamaIndex
            doc = Document(text=text, metadata=metadata.copy())
            
            # Dividir en nodos
            nodes = splitter.get_nodes_from_documents([doc])
            
            # Convertir nodos a formato dict para el resultado
            chunks = []
            for i, node in enumerate(nodes):
                # Combinar metadatos del documento con metadatos específicos del chunk
                chunk_metadata = {
                    **metadata, 
                    "chunk_index": i,
                    "total_chunks": len(nodes)
                }
                
                # Añadir cualquier metadato que el nodo tenga
                if hasattr(node, 'metadata') and node.metadata:
                    chunk_metadata.update(node.metadata)
                
                # Crear estructura para el chunk
                chunks.append({
                    "text": node.text,
                    "metadata": chunk_metadata
                })
            
            logger.info(f"Texto dividido en {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error al fragmentar texto: {e}")
            raise DocumentProcessingError(
                message=f"Error al fragmentar documento: {str(e)}",
                details={"error": str(e)}
            )
    
    @with_context
    async def split_document_intelligently(
        self,
        text: str,
        document_id: str,
        metadata: Dict[str, Any],
        chunk_size: int = None,
        chunk_overlap: int = None,
        ctx: Context = None
    ) -> List[Dict[str, Any]]:
        """Divide un documento de forma inteligente con LlamaIndex.
        
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
        chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP
        
        # Añadir document_id a los metadatos
        doc_metadata = {**metadata, "document_id": document_id}
        
        logger.info(f"Fragmentando documento {document_id} inteligentemente")
        
        try:
            # Usar el método de fragmentación por defecto
            chunks = await self.split_text_into_chunks(
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metadata=doc_metadata,
                ctx=ctx
            )
            
            # Validar número de chunks
            if len(chunks) > settings.MAX_CHUNKS_PER_DOCUMENT:
                logger.warning(
                    f"Documento {document_id} generó {len(chunks)} chunks, "
                    f"excediendo el límite de {settings.MAX_CHUNKS_PER_DOCUMENT}"
                )
                # Truncamos la lista para no sobrepasar el límite
                chunks = chunks[:settings.MAX_CHUNKS_PER_DOCUMENT]
            
            # Enriquecer metadatos de cada chunk con índices actualizados
            for i, chunk in enumerate(chunks):
                chunk["metadata"]["chunk_index"] = i
                chunk["metadata"]["total_chunks"] = len(chunks)
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error al fragmentar documento {document_id}: {e}")
            raise DocumentProcessingError(
                message=f"Error al fragmentar documento {document_id}: {str(e)}",
                details={"document_id": document_id, "error": str(e)}
            )
    
    @with_context
    async def validate_file(
        self,
        file: UploadFile,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """Valida un archivo subido para determinar si puede ser procesado.
        
        Args:
            file: Archivo subido mediante FastAPI
            ctx: Contexto de la operación
            
        Returns:
            Dict[str, Any]: Información del archivo validado
            
        Raises:
            ValidationError: Si el archivo no es válido por alguna razón
        """
        if not file:
            raise ValidationError(
                message="No se proporcionó ningún archivo",
                details={"error": "file_required"}
            )
        
        # Intentar determinar el tipo MIME
        content_type = file.content_type
        filename = file.filename
        extension = os.path.splitext(filename)[1].lower() if filename else ""
        
        # Si no tenemos tipo MIME, intentar inferirlo de la extensión
        if not content_type or content_type == "application/octet-stream":
            content_type = mimetypes.guess_type(filename)[0]
        
        # Si aún no tenemos tipo MIME, ver si es una extensión de texto conocida
        if not content_type and extension in TEXT_EXTENSIONS:
            content_type = TEXT_EXTENSIONS[extension]
        
        # Verificar si podemos procesar este tipo de archivo
        supported = False
        if content_type:
            for mime_pattern, reader in LLAMA_READERS.items():
                if content_type.startswith(mime_pattern.split('/')[0]) and \
                   mime_pattern.split('/')[1] in content_type:
                    supported = True
                    break
        
        if not supported:
            raise ValidationError(
                message=f"Tipo de archivo no soportado: {content_type or 'desconocido'}",
                details={
                    "error": "unsupported_file_type",
                    "content_type": content_type,
                    "filename": filename
                }
            )
        
        # Verificar tamaño
        try:
            file.file.seek(0, os.SEEK_END)
            size = file.file.tell()
            file.file.seek(0)  # Rebobinar para futuras lecturas
            
            if size > settings.MAX_FILE_SIZE:
                raise ValidationError(
                    message=f"El archivo excede el tamaño máximo permitido de {settings.MAX_FILE_SIZE} bytes",
                    details={
                        "error": "file_too_large",
                        "size": size,
                        "max_size": settings.MAX_FILE_SIZE
                    }
                )
                
            # Todo en orden, devolver información del archivo
            return {
                "filename": filename,
                "content_type": content_type,
                "size": size,
                "extension": extension,
                "is_valid": True
            }
                
        except Exception as e:
            if not isinstance(e, ValidationError):
                raise ValidationError(
                    message=f"Error al validar archivo: {str(e)}",
                    details={"error": "validation_error"}
                )
            raise
    
    @with_context
    async def extract_text_from_file(
        self,
        file_path: str,
        mimetype: str,
        metadata: Dict[str, Any] = None,
        ctx: Context = None
    ) -> str:
        """Extrae texto de un archivo usando los readers de LlamaIndex.
        
        Args:
            file_path: Ruta al archivo en el sistema
            mimetype: Tipo MIME del archivo
            metadata: Metadatos adicionales
            ctx: Contexto de la operación
            
        Returns:
            str: Texto extraído del archivo
        """
        logger.info(f"Extrayendo texto de archivo: {file_path}, tipo: {mimetype}")
        metadata = metadata or {}
        
        try:
            # Determinar el reader adecuado
            reader = None
            for mime_pattern, r in LLAMA_READERS.items():
                if mimetype.startswith(mime_pattern.split('/')[0]) and \
                   mime_pattern.split('/')[1] in mimetype:
                    reader = r
                    break
            
            if not reader:
                # Manejar texto plano directamente
                if mimetype == "text/plain" or mimetype.startswith("text/"):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
                else:
                    raise DocumentProcessingError(
                        message=f"No se encontró un reader para el tipo MIME: {mimetype}",
                        details={"mimetype": mimetype, "file_path": file_path}
                    )
            
            # Extraer documentos usando el reader apropiado
            documents = reader.load_data(file_path)
            if not documents:
                return ""
            
            # Combinar el texto de todos los documentos
            all_text = "\n\n".join(doc.text for doc in documents if hasattr(doc, 'text'))
            
            # Verificar longitud del texto
            if len(all_text) > settings.MAX_DOCUMENT_SIZE:
                logger.warning(
                    f"Texto extraído excede tamaño máximo. Truncando de {len(all_text)} "
                    f"a {settings.MAX_DOCUMENT_SIZE} caracteres."
                )
                all_text = all_text[:settings.MAX_DOCUMENT_SIZE]
            
            logger.info(f"Extracción exitosa: {len(all_text)} caracteres")
            return all_text
            
        except Exception as e:
            logger.error(f"Error al extraer texto de {file_path}: {e}")
            raise DocumentProcessingError(
                message=f"Error al extraer texto: {str(e)}",
                details={"file_path": file_path, "mimetype": mimetype}
            )


# Instancia global
chunking_service = ChunkingService()
