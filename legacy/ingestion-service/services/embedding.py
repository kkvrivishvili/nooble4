"""
Funciones centralizadas para generación y almacenamiento de embeddings.

Este módulo centraliza todas las operaciones relacionadas con:
- Generación de embeddings usando el servicio centralizado
- Almacenamiento de chunks con embeddings en vector stores
- Integración con el patrón cache-aside optimizado
"""

import logging
import time
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple, Union

from common.errors import (
    ServiceError, EmbeddingGenerationError,
    handle_errors, ErrorCode
)
from common.context import with_context, Context
from common.utils.http import call_service
from common.cache import invalidate_document_update
from common.tracking import track_token_usage, TOKEN_TYPE_EMBEDDING, OPERATION_EMBEDDING

# Importar configuración centralizada del servicio
from config.settings import get_settings
from config.constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DIMENSION,
    MAX_EMBEDDING_RETRIES,
    TIMEOUTS
)

# Importar componentes de LlamaIndex necesarios
from llama_index.core import Document

logger = logging.getLogger(__name__)

@with_context(tenant=True, validate_tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def generate_embeddings_for_chunks(
    chunks: List[Dict[str, Any]],
    tenant_id: str,
    model: Optional[str] = None,
    collection_id: Optional[str] = None,
    ctx: Context = None
) -> List[Dict[str, Any]]:
    """
    Genera embeddings para una lista de fragmentos.
    
    Args:
        chunks: Lista de fragmentos con texto y metadatos
        tenant_id: ID del tenant
        model: Modelo de embedding a utilizar
        collection_id: ID de la colección para caché
        ctx: Contexto de la operación
        
    Returns:
        List[Dict[str, Any]]: Lista de fragmentos con embeddings
        
    Raises:
        EmbeddingModelError: Si el modelo no está disponible para el tier del tenant
        EmbeddingGenerationError: Si hay un error generando los embeddings
    """
    if not chunks:
        return []
    
    try:
        # Preparar textos y chunk_ids para el batch
        texts = [chunk["text"] for chunk in chunks]
        
        # Extraer chunk_id o generarlos si no existen
        chunk_id_list = []
        for i, chunk in enumerate(chunks):
            # Usar el ID existente o crear uno basado en el índice y documento
            chunk_id = chunk.get("id") or chunk.get("metadata", {}).get("chunk_id")
            if not chunk_id:
                # Si no hay ID, generar uno basado en un hash del texto
                chunk_id = hashlib.md5(chunk["text"].encode()).hexdigest()[:10]
                # Guardar el ID generado en el chunk para consistencia
                chunks[i]["id"] = chunk_id
            chunk_id_list.append(chunk_id)
        
        # Llamar directamente al servicio de embeddings centralizado
        start_time = time.time()
        response = await call_service(
            url=f"{get_settings().embedding_service_url}/internal/embed",
            method="POST",
            headers={"x-tenant-id": tenant_id},
            json={
                "texts": texts,
                "model": model,
                "collection_id": collection_id,  # Incluir collection_id para especificidad en caché
                "chunk_id": chunk_id_list  # Enviar los IDs de chunks para mejor caché y seguimiento
            },
            ctx=ctx
        )
        
        if not response.get("embeddings"):
            raise EmbeddingGenerationError(
                message="El servicio de embeddings no devolvió datos válidos",
                details={"response": response}
            )
        
        # Extraer embeddings y metadatos
        embeddings = response.get("embeddings", [])
        metadata = response.get("metadata", {})
        
        # Registrar uso de tokens si está disponible
        if "token_usage" in metadata and ctx:
            tokens = metadata["token_usage"]
            used_model = model or metadata.get("model", "unknown")
            
            # Generar clave de idempotencia basada en los datos de la operación
            idempotency_key = f"{tenant_id}:{used_model}:{collection_id}:{','.join(chunk_id_list)}"
            
            await track_token_usage(
                tenant_id=tenant_id,
                tokens=tokens,
                model=used_model,
                collection_id=collection_id,
                token_type=TOKEN_TYPE_EMBEDDING,
                operation=OPERATION_EMBEDDING,
                metadata={
                    "chunk_count": len(chunks),
                    "service": "ingestion"
                },
                idempotency_key=idempotency_key
            )
        
        execution_time = time.time() - start_time
        logger.info(f"Embeddings generados para {len(texts)} textos en {execution_time:.2f}s")
        
        # Verificar resultados
        if len(embeddings) != len(chunks):
            raise EmbeddingGenerationError(
                message=f"Discrepancia en el número de embeddings: {len(embeddings)} vs {len(chunks)} fragmentos",
                details={"chunks_count": len(chunks), "embeddings_count": len(embeddings)}
            )
        
        # Añadir embeddings a los fragmentos
        result = []
        for i, chunk in enumerate(chunks):
            chunk_with_embedding = chunk.copy()
            chunk_with_embedding["embedding"] = embeddings[i]
            result.append(chunk_with_embedding)
        
        logger.info(f"Embeddings generados para {len(result)} fragmentos usando LlamaIndex")
        return result
        
    except Exception as e:
        logger.error(f"Error generando embeddings: {str(e)}")
        if isinstance(e, ServiceError):
            raise
        
        raise EmbeddingGenerationError(
            message=f"Error generando embeddings: {str(e)}",
            details={
                "model": model,
                "chunks_count": len(chunks) if chunks else 0
            }
        )

@with_context(tenant=True, validate_tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def process_and_store_chunks(
    chunks: List[Dict[str, Any]],
    tenant_id: str,
    collection_id: str,
    document_id: str,
    model: Optional[str] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Procesa fragmentos, genera embeddings y almacena en Supabase.
    
    Args:
        chunks: Lista de fragmentos con texto y metadatos
        tenant_id: ID del tenant
        collection_id: ID de la colección
        document_id: ID del documento
        model: Modelo de embeddings a utilizar
        ctx: Contexto de la operación
        
    Returns:
        Dict[str, Any]: Estadísticas del procesamiento
    """
    # Usar directamente el módulo central de LlamaIndex para todo el proceso
    return await store_chunks_in_vector_store(
        chunks=chunks,
        tenant_id=tenant_id,
        collection_id=collection_id,
        document_id=document_id,
        embedding_model=model,
        ctx=ctx
    )

# Implementación eliminada: generate_embeddings_with_llama_index
# Esta función era redundante ya que simplemente llamaba al servicio centralizado.
# Cualquier uso de esta función debe reemplazarse por una llamada directa a
# call_service con el endpoint /internal/embed del servicio de embedding.

# Implementación para crear vector stores en Supabase
async def create_supabase_vector_store(
    tenant_id: str,
    collection_id: str,
    embedding_dimension: int = 1536,
    ctx: Context = None
):
    """
    Crea o verifica un vector store en Supabase usando LlamaIndex.
    
    Args:
        tenant_id: ID del tenant
        collection_id: ID de la colección
        embedding_dimension: Dimensión de los embeddings
        ctx: Contexto de la operación
        
    Returns:
        SupabaseVectorStore: Instancia del vector store
    """
    from llama_index_vector_stores_supabase import SupabaseVectorStore
    
    try:
        # Construir el nombre de la tabla de vectores
        table_name = f"vectors_{tenant_id}_{collection_id}"
        logger.info(f"Usando tabla de vectores: {table_name}")
        
        # Crear instancia de SupabaseVectorStore
        vector_store = SupabaseVectorStore(
            postgres_connection_string=settings.supabase_connection_string,
            collection_name=table_name,
            dimension=embedding_dimension,
            engine="vecs"  # Asegurarse de usar el motor vecs
        )
        
        return vector_store
    
    except Exception as e:
        logger.error(f"Error creando vector store: {str(e)}")
        raise ServiceError(
            message=f"Error al crear vector store para colección {collection_id}: {str(e)}",
            error_code=ErrorCode.VECTOR_STORE_ERROR,
            details={
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "error": str(e)
            }
        )

@with_context(tenant=True, validate_tenant=True)
@handle_errors(error_type="service", log_traceback=True)
async def store_chunks_in_vector_store(
    chunks: List[Dict[str, Any]],
    tenant_id: str,
    collection_id: str,
    document_id: str,
    embedding_model: str = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Almacena chunks con sus embeddings en el vector store de Supabase.
    
    Args:
        chunks: Lista de chunks con texto y metadatos
        tenant_id: ID del tenant
        collection_id: ID de la colección
        document_id: ID del documento
        embedding_model: Modelo de embeddings a utilizar
        ctx: Contexto de la operación
        
    Returns:
        Dict[str, Any]: Estadísticas del procesamiento
    """
    start_time = time.time()
    
    # Validaciones básicas
    if not chunks:
        logger.warning("No hay chunks para almacenar en el vector store")
        return {
            "chunks_stored": 0,
            "execution_time": 0,
            "document_id": document_id
        }
    
    try:
        # Generar embeddings si no los tienen
        chunks_with_embeddings = chunks
        if any("embedding" not in chunk for chunk in chunks):
            logger.info("Generando embeddings para chunks sin ellos")
            chunks_with_embeddings = await generate_embeddings_for_chunks(
                chunks=chunks,
                tenant_id=tenant_id,
                model=embedding_model,
                collection_id=collection_id,
                ctx=ctx
            )
        
        # Crear documentos para LlamaIndex
        llama_docs = []
        for chunk in chunks_with_embeddings:
            # Extraer texto y embedding
            text = chunk["text"]
            embedding = chunk.get("embedding")
            
            # Crear metadata normalizada
            metadata = chunk.get("metadata", {}).copy()
            metadata.update({
                "document_id": document_id,
                "chunk_id": chunk.get("id", hashlib.md5(text.encode()).hexdigest()[:10]),
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "embedding_model": embedding_model or settings.default_embedding_model,  # Registrar modelo utilizado
                "embedding_timestamp": int(time.time())  # Registrar cuándo se creó el embedding
            })
            
            # Crear documento de LlamaIndex
            llama_doc = Document(
                text=text,
                metadata=metadata,
                embedding=embedding,
                id_=metadata["chunk_id"],  # Usar el chunk_id para consistencia
                embedding_model=embedding_model or settings.default_embedding_model  # Incluir explicitamente el modelo usado
            )
            llama_docs.append(llama_doc)
        
        # Crear o acceder al vector store
        embedding_dim = len(chunks_with_embeddings[0].get("embedding", [])) if chunks_with_embeddings else 1536
        vector_store = await create_supabase_vector_store(
            tenant_id=tenant_id,
            collection_id=collection_id,
            embedding_dimension=embedding_dim,
            ctx=ctx
        )
        
        # Almacenar en Supabase
        from llama_index.core import VectorStoreIndex, StorageContext
        
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex(llama_docs, storage_context=storage_context)
        
        # Invalidación estratégica de caché utilizando las funciones centralizadas
        # Esta invalidación asegura que cualquier consulta que dependa de este documento
        # obtenga resultados actualizados tras esta modificación
        await invalidate_document_update(
            tenant_id=tenant_id,
            collection_id=collection_id,
            document_id=document_id,
            metadata={
                "updated_chunks": len(llama_docs),
                "timestamp": int(time.time())
            },
            ctx=ctx
        )
        
        execution_time = time.time() - start_time
        result = {
            "chunks_stored": len(llama_docs),
            "execution_time": execution_time,
            "document_id": document_id
        }
        
        logger.info(f"Almacenados {len(llama_docs)} chunks en {execution_time:.2f}s")
        return result
        
    except Exception as e:
        logger.error(f"Error en store_chunks_in_vector_store: {str(e)}")
        if isinstance(e, ServiceError):
            raise
        
        raise ServiceError(
            message=f"Error almacenando chunks en vector store: {str(e)}",
            error_code=ErrorCode.VECTOR_STORE_ERROR,
            details={
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "document_id": document_id,
                "chunks_count": len(chunks)
            }
        )