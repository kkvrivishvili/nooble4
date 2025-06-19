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
    SimpleChatPayload,
    SimpleChatResponse,
    ChatMessage,
    ChatCompletionRequest,
    EmbeddingRequest,
    TokenUsage
)
from ..clients.groq_client import GroqClient
from ..clients.vector_client import VectorClient
from ..clients.embedding_client import EmbeddingClient


class SimpleHandler(BaseHandler):
    """Handler para procesamiento de chat simple con RAG automático."""
    
    def __init__(self, app_settings, embedding_client: EmbeddingClient, direct_redis_conn=None):
        """
        Inicializa el handler.
        
        Args:
            app_settings: QueryServiceSettings
            embedding_client: Cliente para obtener embeddings
            direct_redis_conn: Conexión Redis directa
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
        
        self._logger.info("SimpleHandler inicializado")
    
    async def process_simple_query(
        self,
        payload: SimpleChatPayload,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID
    ) -> SimpleChatResponse:
        """Procesa una consulta simple con RAG automático."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Validar que tenemos todos los parámetros requeridos (Pydantic ya lo hace en parte)
            self._validate_payload(payload)

            # 1. Preparar request de embeddings (compatible con OpenAI)
            embedding_request = EmbeddingRequest(
                model=payload.embedding_model,
                input=payload.user_message,
                dimensions=payload.embedding_dimensions
            )

            # 2. Obtener embedding
            query_embedding = await self._get_query_embedding(
                embedding_request=embedding_request,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id
            )

            # 3. Buscar en vector store
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=payload.collection_ids,
                top_k=payload.top_k,
                similarity_threshold=payload.similarity_threshold,
                tenant_id=tenant_id,
                filters={"document_ids": payload.document_ids} if payload.document_ids else None
            )

            # 4. Construir mensajes para Groq
            messages: List[ChatMessage] = []

            # System message siempre presente
            if payload.system_prompt:
                messages.append(ChatMessage(
                    role="system",
                    content=payload.system_prompt
                ))

            # Agregar historial
            if payload.conversation_history:
                messages.extend(payload.conversation_history)

            # Agregar contexto RAG
            if search_results:
                context = self._build_context(search_results)
                messages.append(ChatMessage(
                    role="system",
                    content=f"Context information:\n{context}"
                ))

            # Agregar mensaje del usuario
            messages.append(ChatMessage(
                role="user",
                content=payload.user_message
            ))

            # 5. Preparar request para Groq
            chat_request = ChatCompletionRequest(
                model=payload.chat_model,
                messages=messages,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                top_p=payload.top_p,
                frequency_penalty=payload.frequency_penalty,
                presence_penalty=payload.presence_penalty,
                stop=payload.stop
            )

            # 6. Llamar a Groq
            groq_client = GroqClient(
                api_key=self.app_settings.groq_api_key,
                timeout=payload.max_tokens // 100 if payload.max_tokens else 30
            )
            
            response = await groq_client.chat.completions.create(
                **chat_request.model_dump(exclude_none=True)
            )

            # 7. Construir respuesta unificada
            response_message_content = ""
            if response.choices and response.choices[0].message:
                response_message_content = response.choices[0].message.content
            
            response_token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            if response.usage:
                response_token_usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )

            execution_time_ms = int((time.time() - start_time) * 1000)
            final_sources = list(set(r.document_id for r in search_results if r.document_id))

            return SimpleChatResponse(
                message=response_message_content,
                sources=final_sources,
                usage=response_token_usage,
                query_id=query_id,
                conversation_id=str(uuid4()),
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            self._logger.error(f"Error en simple query: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando query simple: {str(e)}")
    
    def _validate_payload(self, payload: SimpleChatPayload):
        """Valida que el payload tenga todos los campos requeridos."""
        # Validación adicional si es necesaria
        pass
    
    async def _get_query_embedding(
        self,
        embedding_request: EmbeddingRequest,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID
    ) -> List[float]:
        """Obtiene el embedding de la consulta usando el Embedding Service."""
        response = await self.embedding_client.request_query_embedding(
            query_text=embedding_request.input if isinstance(embedding_request.input, str) else embedding_request.input[0],
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            model=embedding_request.model,
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        return response.data.get("embedding", [])
    
    def _build_context(self, search_results) -> str:
        """Construye el contexto a partir de los resultados de búsqueda."""
        if not search_results:
            return "No se encontró información relevante."
        
        context_parts = []
        for result in search_results[:5]:  
            context_parts.append(f"[Fuente: {result.collection_id}] {result.content}")
        
        return "\n\n".join(context_parts)