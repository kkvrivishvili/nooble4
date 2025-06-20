"""
Handler para chat simple con RAG automático.
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError
from common.models.chat_models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    EmbeddingRequest,
    TokenUsage,
    RAGConfig
)

from ..clients.groq_client import GroqClient
from ..clients.vector_client import VectorClient
from ..clients.embedding_client import EmbeddingClient


class SimpleHandler(BaseHandler):
    """Handler para procesamiento de chat simple con RAG automático."""
    
    def __init__(self, app_settings, embedding_client: EmbeddingClient, direct_redis_conn=None):
        """
        Inicializa el handler.
        """
        super().__init__(app_settings, direct_redis_conn)
        
        if not embedding_client:
            raise ValueError("embedding_client es requerido para SimpleHandler")
            
        self.embedding_client = embedding_client
        
        # TODO: Cambiar a Qdrant local cuando esté implementado
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.search_timeout_seconds
        )
        
        self.logger.info("SimpleHandler inicializado")
    
async def process_simple_query(
    self,
    payload: ChatRequest,
    tenant_id: str,
    session_id: str,
    task_id: UUID,
    trace_id: UUID,
    correlation_id: UUID
) -> ChatResponse:
    """Procesa una consulta simple con RAG automático."""
    start_time = time.time()
    conversation_id = str(correlation_id) if correlation_id else str(uuid4())
    
    try:
        # Extraer mensaje del usuario (último mensaje con role="user")
        user_message = None
        for msg in reversed(payload.messages):
            if msg.role == "user" and msg.content:
                user_message = msg.content
                break
        
        if not user_message:
            raise AppValidationError("No se encontró mensaje del usuario")
        
        self.logger.info(
            f"Procesando simple query: '{user_message[:50]}...'",
            extra={
                "query_id": conversation_id,
                "tenant_id": tenant_id,
                "collections": payload.rag_config.collection_ids if payload.rag_config else []
            }
        )
        
        # Si hay configuración RAG, hacer búsqueda
        sources = []
        if payload.rag_config:
            # 1. Obtener embedding de la consulta
            embedding_request = EmbeddingRequest(
                input=user_message,
                model=payload.rag_config.embedding_model,
                dimensions=payload.rag_config.embedding_dimensions
            )
            
            query_embedding = await self._get_query_embedding(
                embedding_request=embedding_request,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id
            )
            
            # 2. Buscar en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=payload.rag_config.collection_ids,
                top_k=payload.rag_config.top_k,
                similarity_threshold=payload.rag_config.similarity_threshold,
                tenant_id=tenant_id,
                filters={"document_ids": payload.rag_config.document_ids} if payload.rag_config.document_ids else None
            )
            
            # 3. Si hay resultados, agregar contexto
            if search_results:
                context = self._build_context(search_results)
                # Insertar contexto como mensaje del sistema después del primer mensaje
                context_msg = ChatMessage(
                    role="system",
                    content=f"Context information:\n{context}"
                )
                # Clonar mensajes y agregar contexto
                messages_with_context = payload.messages.copy()
                messages_with_context.insert(1, context_msg)  # Después del system prompt
                payload.messages = messages_with_context
                
                # Extraer sources
                sources = list(set(
                    r.document_id for r in search_results 
                    if hasattr(r, 'document_id') and r.document_id
                ))
        
        # 4. Crear cliente Groq y llamar
        groq_client = GroqClient(
            api_key=self.app_settings.groq_api_key,
            timeout=60
        )
        
        # Preparar mensajes para Groq (convertir a dict)
        groq_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in payload.messages
            if msg.content  # Solo mensajes con contenido
        ]
        
        # Llamar a Groq
        groq_response = await groq_client.client.chat.completions.create(
            messages=groq_messages,
            model=payload.model.value,  # Usar el valor del enum
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            top_p=payload.top_p,
            frequency_penalty=payload.frequency_penalty,
            presence_penalty=payload.presence_penalty,
            stop=payload.stop
        )
        
        # 5. Construir respuesta
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        response_message = ChatMessage(
            role="assistant",
            content=groq_response.choices[0].message.content
        )
        
        return ChatResponse(
            message=response_message,
            usage=TokenUsage(
                prompt_tokens=groq_response.usage.prompt_tokens,
                completion_tokens=groq_response.usage.completion_tokens,
                total_tokens=groq_response.usage.total_tokens
            ),
            conversation_id=conversation_id,
            execution_time_ms=execution_time_ms,
            sources=sources
        )
        
    except Exception as e:
        self.logger.error(f"Error en simple query: {e}", exc_info=True)
        raise ExternalServiceError(f"Error procesando query simple: {str(e)}")
    
    async def _get_query_embedding(
        self,
        embedding_request: EmbeddingRequest,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID
    ) -> List[float]:
        """Obtiene el embedding de la consulta usando el Embedding Service."""
        # Usar el embedding client para obtener el embedding
        response = await self.embedding_client.request_query_embedding(
            query_text=embedding_request.input,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            model=embedding_request.model
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        return response.data.get("embedding", [])
    
    def _build_context(self, search_results, max_results: int = 5) -> str:
        """Construye el contexto a partir de los resultados de búsqueda."""
        if not search_results:
            return ""
        
        context_parts = []
        for i, result in enumerate(search_results[:max_results]):
            source_info = f"[Source {i+1}: {result.collection_id}"
            if hasattr(result, 'document_id') and result.document_id:
                source_info += f"/{result.document_id}"
            source_info += f", Score: {result.similarity_score:.3f}]"
            
            context_parts.append(f"{source_info}\n{result.content}")
        
        return "\n\n".join(context_parts)