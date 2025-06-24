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
        """
        super().__init__(app_settings, direct_redis_conn)
        
        if not embedding_client:
            raise ValueError("embedding_client es requerido para SimpleHandler")
            
        self.embedding_client = embedding_client
        
        # Inicializar vector client
        self.vector_client = VectorClient(
            base_url=str(app_settings.qdrant_url) if hasattr(app_settings, 'qdrant_url') and app_settings.qdrant_url else "http://localhost:6333",
            timeout=app_settings.search_timeout_seconds
        )
        
        self.logger.info("SimpleHandler inicializado")
    
    async def process_simple_query(
        self,
        data: Dict[str, Any],
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        correlation_id: UUID,
        agent_id: UUID,
    ) -> ChatResponse:
        """Procesa una consulta simple con RAG automático."""
        start_time = time.time()
        conversation_id = str(correlation_id) if correlation_id else str(uuid4())
        
        try:
            # Extraer configuraciones del payload preparado por agent_execution_service
            raw_messages = data.get("messages", [])
            query_config_data = data.get("query_config")
            rag_config_data = data.get("rag_config")
            
            # Validar datos requeridos
            if not raw_messages:
                raise AppValidationError("messages es requerido")
            if not query_config_data:
                raise AppValidationError("query_config es requerido")
            
            # Parsear configuraciones
            from common.models.config_models import QueryConfig, RAGConfig
            query_config = QueryConfig.model_validate(query_config_data)
            rag_config = RAGConfig.model_validate(rag_config_data) if rag_config_data else None
            
            # Validaciones específicas de Query Service para query_config
            self._validate_query_config(query_config)
            
            # Validaciones específicas de Query Service para rag_config (si está presente)
            if rag_config:
                self._validate_rag_config(rag_config)
            
            # Convertir raw messages a ChatMessage objects
            messages = []
            for msg_data in raw_messages:
                if isinstance(msg_data, dict):
                    messages.append(ChatMessage.model_validate(msg_data))
                else:
                    messages.append(msg_data)  # Ya es ChatMessage
            
            # Extraer mensaje del usuario (último mensaje con role="user")
            user_message = None
            for msg in reversed(messages):
                if msg.role == "user" and msg.content:
                    user_message = msg.content
                    break
            
            if not user_message:
                raise AppValidationError("No se encontró mensaje del usuario")
            
            self.logger.info(
                f"Procesando simple query: '{user_message[:50]}...'",
                extra={
                    "query_id": conversation_id,
                    "tenant_id": str(tenant_id),
                    "collections": rag_config.collection_ids if rag_config else []
                }
            )
            
            # Copiar mensajes originales para construir el payload final
            final_messages = messages.copy()
            sources = []
            
            # ORQUESTACIÓN RAG: Si hay configuración RAG, hacer búsqueda
            if rag_config:
                # 1. Obtener embedding de la consulta
                embedding_request = EmbeddingRequest(
                    input=user_message,
                    model=rag_config.embedding_model,
                    dimensions=rag_config.embedding_dimensions
                )
                
                query_embedding = await self._get_query_embedding(
                    embedding_request=embedding_request,
                    rag_config=rag_config,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id,
                    agent_id=agent_id
                )
                
                # 2. Buscar en vector store
                search_results = await self.vector_client.search(
                    query_embedding=query_embedding,
                    collection_ids=rag_config.collection_ids,
                    top_k=rag_config.top_k,
                    similarity_threshold=rag_config.similarity_threshold,
                    tenant_id=str(tenant_id),
                    filters={"document_ids": rag_config.document_ids} if rag_config.document_ids else None
                )
                
                # 3. FORMATO GROQ: Inyectar contexto como ChatMessage con role="system" antes del último user message
                if search_results:
                    context = self._build_context(search_results, max_results=rag_config.top_k)
                    
                    # Crear mensaje de contexto siguiendo las mejores prácticas del SDK de Groq
                    context_msg = ChatMessage(
                        role="system",
                        content=f"Información de contexto relevante:\n{context}"
                    )
                    
                    # Insertar el contexto justo antes del último mensaje del usuario para máxima relevancia
                    # Encontrar la posición del último mensaje del usuario
                    user_msg_index = None
                    for i in range(len(final_messages) - 1, -1, -1):
                        if final_messages[i].role == "user":
                            user_msg_index = i
                            break
                    
                    if user_msg_index is not None:
                        # Insertar contexto justo antes del último mensaje del usuario
                        final_messages.insert(user_msg_index, context_msg)
                    else:
                        # Fallback: agregar al final si no se encuentra user message
                        final_messages.append(context_msg)
                    
                    # Extraer sources para la respuesta
                    sources = [UUID(chunk.chunk_id) for chunk in search_results]
            
            # CONSTRUCCIÓN DEL SYSTEM PROMPT desde query_config
            # Si ya hay un system message, lo actualizamos. Si no, lo creamos
            system_prompt = query_config.system_prompt_template
            
            # Verificar si ya existe un system message
            has_system_msg = any(msg.role == "system" for msg in final_messages)
            if not has_system_msg:
                # Agregar system prompt al inicio
                system_msg = ChatMessage(role="system", content=system_prompt)
                final_messages.insert(0, system_msg)
            else:
                # Actualizar el primer system message encontrado
                for msg in final_messages:
                    if msg.role == "system":
                        msg.content = system_prompt
                        break
            
            # LLAMADA A GROQ: Formatear payload según especificaciones oficiales del SDK
            groq_payload = {
                "messages": [{"role": msg.role, "content": msg.content} for msg in final_messages],
                "model": query_config.model.value,  # Usar el enum ChatModel
                "temperature": query_config.temperature,
                "max_tokens": query_config.max_tokens,
                "top_p": query_config.top_p,
                "frequency_penalty": query_config.frequency_penalty,
                "presence_penalty": query_config.presence_penalty,
                "stop": query_config.stop_sequences if query_config.stop_sequences else None
            }
            
            # Llamar al cliente de Groq
            response_text, token_usage = await self.groq_client.create_completion(**groq_payload)
            
            # Construir respuesta
            end_time = time.time()
            response = ChatResponse(
                conversation_id=UUID(conversation_id),
                content=response_text,
                model=query_config.model,
                usage=token_usage,
                sources=sources,
                processing_time=end_time - start_time
            )
            
            self.logger.info(
                f"Simple query procesada exitosamente. Tokens: {token_usage.total_tokens}",
                extra={
                    "query_id": conversation_id,
                    "processing_time": response.processing_time,
                    "context_chunks": len(sources)
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error procesando simple query: {str(e)}", exc_info=True)
            if isinstance(e, (AppValidationError, ExternalServiceError)):
                raise
            raise ExternalServiceError(f"Error interno en simple query: {str(e)}")
    
    async def _get_query_embedding(
        self,
        embedding_request: EmbeddingRequest,
        rag_config: RAGConfig,
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        trace_id: UUID,
        agent_id: UUID,
    ) -> List[float]:
        """Obtiene el embedding de la consulta usando el Embedding Service con configuración RAG."""
        # Usar el embedding client refactorizado para obtener el embedding
        response = await self.embedding_client.get_embeddings(
            texts=[embedding_request.input],
            rag_config=rag_config,
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            trace_id=trace_id
        )
        
        if not response.success or not response.data:
            raise ExternalServiceError("Error obteniendo embedding del Embedding Service")
            
        # El response.data debería contener una lista de embeddings para los textos
        embeddings = response.data.get("embeddings", [])
        if not embeddings or len(embeddings) == 0:
            raise ExternalServiceError("No se recibió embedding del Embedding Service")
            
        # Retornamos el primer embedding (corresponde a la consulta)
        return embeddings[0]
    
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
    
    def _validate_query_config(self, query_config: QueryConfig):
        # Validar campos requeridos
        if not query_config.model:
            raise AppValidationError("Modelo de lenguaje es requerido")
        if not query_config.system_prompt_template:
            raise AppValidationError("Plantilla de prompt del sistema es requerida")
        if not query_config.temperature:
            raise AppValidationError("Temperatura es requerida")
        if not query_config.max_tokens:
            raise AppValidationError("Cantidad máxima de tokens es requerida")
        if not query_config.top_p:
            raise AppValidationError("Umbral de probabilidad es requerido")
        if not query_config.frequency_penalty:
            raise AppValidationError("Penalización de frecuencia es requerida")
        if not query_config.presence_penalty:
            raise AppValidationError("Penalización de presencia es requerida")
        
        # Validar valores válidos
        if query_config.temperature < 0 or query_config.temperature > 1:
            raise AppValidationError("Temperatura debe estar entre 0 y 1")
        if query_config.max_tokens < 1:
            raise AppValidationError("Cantidad máxima de tokens debe ser mayor que 0")
        if query_config.top_p < 0 or query_config.top_p > 1:
            raise AppValidationError("Umbral de probabilidad debe estar entre 0 y 1")
        if query_config.frequency_penalty < 0 or query_config.frequency_penalty > 1:
            raise AppValidationError("Penalización de frecuencia debe estar entre 0 y 1")
        if query_config.presence_penalty < 0 or query_config.presence_penalty > 1:
            raise AppValidationError("Penalización de presencia debe estar entre 0 y 1")
    
    def _validate_rag_config(self, rag_config: RAGConfig):
        # Validar campos requeridos
        if not rag_config.collection_ids:
            raise AppValidationError("IDs de colección son requeridos")
        if not rag_config.embedding_model:
            raise AppValidationError("Modelo de embedding es requerido")
        if not rag_config.embedding_dimensions:
            raise AppValidationError("Dimensiones de embedding son requeridas")
        if not rag_config.top_k:
            raise AppValidationError("Cantidad de resultados es requerida")
        if not rag_config.similarity_threshold:
            raise AppValidationError("Umbral de similitud es requerido")
        
        # Validar valores válidos
        if rag_config.top_k < 1:
            raise AppValidationError("Cantidad de resultados debe ser mayor que 0")
        if rag_config.similarity_threshold < 0 or rag_config.similarity_threshold > 1:
            raise AppValidationError("Umbral de similitud debe estar entre 0 y 1")