"""
Handler para chat simple con RAG automático.
"""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID, uuid4

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError, AppValidationError

from ..models import (
    QuerySimplePayload,
    QuerySimpleResponseData,
    TokenUsage,
    QueryServiceChatMessage
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
        payload: QuerySimplePayload,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID
    ) -> QuerySimpleResponseData:
        """Procesa una consulta simple con RAG automático."""
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Validar que tenemos todos los parámetros requeridos
            self._validate_payload(payload)
            
            # 1. Obtener embedding de la consulta
            query_embedding = await self._get_query_embedding(
                query_text=payload.user_message,
                embedding_config=payload.embedding_config,
                tenant_id=tenant_id,
                session_id=session_id,
                task_id=task_id,
                trace_id=trace_id
            )
            
            # 2. Buscar en vector store
            # TODO: Implementar búsqueda en Qdrant local
            search_results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=payload.collection_ids,
                top_k=payload.top_k,
                similarity_threshold=payload.similarity_threshold,
                tenant_id=tenant_id,
                filters={"document_ids": payload.document_ids} if payload.document_ids else None
            )
            
            # 3. Construir contexto con los chunks encontrados
            context = self._build_context(search_results)
            sources = list(set(r.document_id for r in search_results if r.document_id))
            
            # 4. Generar respuesta con LLM
            groq_client = GroqClient(
                api_key=self.app_settings.groq_api_key,
                timeout=payload.agent_config.max_tokens // 100  # Aproximación basada en tokens
            )
            
            prompt = self._build_prompt(
                user_message=payload.user_message,
                context=context,
                conversation_history=payload.conversation_history
            )
            
            response, token_usage = await groq_client.generate(
                prompt=prompt,
                system_prompt=payload.system_prompt,
                model=payload.agent_config.model_name,
                temperature=payload.agent_config.temperature,
                max_tokens=payload.agent_config.max_tokens,
                top_p=payload.agent_config.top_p,
                frequency_penalty=payload.agent_config.frequency_penalty,
                presence_penalty=payload.agent_config.presence_penalty,
                stop=payload.agent_config.stop_sequences
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return QuerySimpleResponseData(
                message=response,
                sources=sources,
                usage=TokenUsage(**token_usage),
                query_id=query_id,
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            self._logger.error(f"Error en simple query: {e}", exc_info=True)
            raise ExternalServiceError(f"Error procesando query simple: {str(e)}")
    
    def _validate_payload(self, payload: QuerySimplePayload):
        """Valida que el payload tenga todos los campos requeridos."""
        # Validación adicional si es necesaria
        pass
    
    async def _get_query_embedding(
        self,
        query_text: str,
        embedding_config: dict,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID
    ) -> List[float]:
        """Obtiene el embedding de la consulta usando el Embedding Service."""
        response = await self.embedding_client.request_query_embedding(
            query_text=query_text,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            model=embedding_config.model
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        return response.data.get("embedding", [])
    
    def _build_context(self, search_results) -> str:
        """Construye el contexto a partir de los resultados de búsqueda."""
        if not search_results:
            return "No se encontró información relevante."
        
        context_parts = []
        for result in search_results[:5]:  # Limitar a top 5
            context_parts.append(f"[Fuente: {result.collection_id}] {result.content}")
        
        return "\n\n".join(context_parts)
    
    def _build_prompt(
        self,
        user_message: str,
        context: str,
        conversation_history: List[QueryServiceChatMessage]
    ) -> str:
        """Construye el prompt final para el LLM."""
        prompt_parts = []
        
        # Agregar historial si existe
        if conversation_history:
            prompt_parts.append("Conversación previa:")
            for msg in conversation_history[-5:]:  # Últimos 5 mensajes
                prompt_parts.append(f"{msg.role}: {msg.content}")
            prompt_parts.append("")
        
        # Agregar contexto
        prompt_parts.append("Información relevante:")
        prompt_parts.append(context)
        prompt_parts.append("")
        
        # Agregar pregunta actual
        prompt_parts.append("Pregunta actual:")
        prompt_parts.append(user_message)
        
        return "\n".join(prompt_parts)