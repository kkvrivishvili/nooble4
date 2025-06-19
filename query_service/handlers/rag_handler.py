"""
Handler para procesamiento RAG (Retrieval-Augmented Generation).

Este handler orquesta el flujo completo de RAG:
1. Obtener embeddings de la consulta
2. Buscar documentos relevantes
3. Construir prompt con contexto
4. Generar respuesta usando LLM
"""

import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
import json

from common.handlers import BaseHandler
from common.errors.exceptions import ExternalServiceError

from ..models import (
    QueryGeneratePayload, # Added
    QueryGenerateResponseData,
    SearchResultData,
    QueryServiceChatMessage
)
from ..models.base_models import TokenUsage, RetrievedDoc # Added
from ..clients.groq_client import GroqClient
from ..clients.vector_client import VectorClient


class RAGHandler(BaseHandler):
    """
    Handler para procesamiento completo de consultas RAG.
    
    Coordina la búsqueda vectorial con la generación de respuestas
    usando LLMs para proporcionar respuestas contextualizadas.
    """
    
    def __init__(self, app_settings, direct_redis_conn=None):
        """
        Inicializa el handler con sus dependencias.
        
        Args:
            app_settings: QueryServiceSettings
            direct_redis_conn: Conexión Redis para operaciones directas
        """
        super().__init__(app_settings, direct_redis_conn)
        
        # Inicializar clientes
        self.groq_client = GroqClient(
            api_key=app_settings.groq_api_key,
            timeout=app_settings.llm_timeout_seconds,
            max_retries=app_settings.groq_max_retries
        )
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.search_timeout_seconds
        )
        
        # Configuración
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        self.default_llm_model = app_settings.default_llm_model
        self.llm_temperature = app_settings.llm_temperature
        self.llm_max_tokens = app_settings.llm_max_tokens
        self.llm_top_p = app_settings.llm_top_p
        self.llm_frequency_penalty = app_settings.llm_frequency_penalty
        self.llm_presence_penalty = app_settings.llm_presence_penalty
        self.available_models = app_settings.available_models
        
        self._logger.info("RAGHandler inicializado")
    
    async def process_rag_query(
        self,
        payload: QueryGeneratePayload,
        tenant_id: str, # Retained for logging/operational context
        session_id: str, # Retained for logging/operational context
        task_id: Optional[UUID] = None, # Retained for logging/operational context
        trace_id: Optional[UUID] = None, # Retained for operational context
        correlation_id: Optional[UUID] = None, # Used for query_id
        embedding_client=None # Specific to handler's embedding strategy
    ) -> QueryGenerateResponseData:
        """
        Procesa una consulta RAG completa utilizando QueryGeneratePayload.
        
        Args:
            payload: QueryGeneratePayload con todos los datos de la consulta.
            tenant_id: ID del tenant.
            session_id: ID de sesión.
            task_id: ID de la tarea (opcional).
            trace_id: ID de traza (opcional).
            correlation_id: ID de correlación (opcional), usado para query_id.
            embedding_client: Cliente de embedding (opcional).
            
        Returns:
            QueryGenerateResponseData con la respuesta generada.
        """
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(UUID())

        # Extract parameters from payload
        query_text = payload.query_text
        collection_ids = payload.collection_ids
        conversation_history = payload.conversation_history
        system_prompt_template = payload.system_prompt_template
        
        # Effective RAG parameters from payload or handler defaults
        top_k_eff = payload.top_k_retrieval # Uses default from QueryGeneratePayload if not set by caller
        similarity_threshold_eff = payload.similarity_threshold if payload.similarity_threshold is not None else self.similarity_threshold

        # Effective LLM parameters from payload.llm_config or handler defaults
        qs_llm_config = payload.llm_config
        llm_model_eff = qs_llm_config.model_name if qs_llm_config.model_name else self.default_llm_model
        temperature_eff = qs_llm_config.temperature if qs_llm_config.temperature is not None else self.llm_temperature
        max_tokens_eff = qs_llm_config.max_tokens if qs_llm_config.max_tokens is not None else self.llm_max_tokens
        top_p_eff = qs_llm_config.top_p # Can be None, Groq client handles default
        frequency_penalty_eff = qs_llm_config.frequency_penalty # Can be None
        presence_penalty_eff = qs_llm_config.presence_penalty # Can be None

        effective_system_prompt = system_prompt_template if system_prompt_template is not None else self._get_default_system_prompt()

        self._logger.info(
            f"Procesando consulta RAG: '{query_text[:50]}...' en colecciones {collection_ids}",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "task_id": str(task_id) if task_id else None,
                "collections": collection_ids,
                "llm_model": llm_model_eff
            }
        )
        
        try:
            # 1. Obtener embeddings de la consulta
            search_start = time.time()
            query_embedding = await self._get_query_embedding(
                query_text, 
                tenant_id, 
                session_id,
                trace_id,
                embedding_client,
                task_id
            )
            
            # 2. Buscar documentos relevantes (returns List[SearchResultData])
            search_results_raw = await self._search_documents(
                query_text=query_text,
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k_eff,
                similarity_threshold=similarity_threshold_eff,
                tenant_id=tenant_id
            )
            search_time_ms = int((time.time() - search_start) * 1000)

            # Convert SearchResultData to RetrievedDoc for the response model
            retrieved_docs_for_response = [
                RetrievedDoc(
                    doc_id=sr.id,
                    content=sr.content,
                    metadata=sr.metadata,
                    score=sr.score,
                    collection_name=sr.collection_id
                ) for sr in search_results_raw
            ]
            
            # 3. Construir prompt con contexto (using List[SearchResultData] or List[RetrievedDoc] - should be consistent)
            # _build_rag_prompt expects List[SearchResultData], so pass search_results_raw
            prompt = self._build_rag_prompt(
                query_text=query_text,
                search_results=search_results_raw, # Pass raw results here
                conversation_history=conversation_history
            )
            
            # 4. Generar respuesta
            generation_start = time.time()
            generated_text_response, token_usage_dict = await self._generate_response(
                prompt=prompt,
                system_prompt=effective_system_prompt,
                model=llm_model_eff,
                temperature=temperature_eff,
                max_tokens=max_tokens_eff,
                top_p=top_p_eff,
                frequency_penalty=frequency_penalty_eff,
                presence_penalty=presence_penalty_eff
            )
            generation_time_ms = int((time.time() - generation_start) * 1000)
            
            # 5. Construir respuesta
            total_time_ms = int((time.time() - start_time) * 1000)

            llm_info_for_response = {"model_name": llm_model_eff, "provider": "groq"} # Example
            token_usage_for_response = TokenUsage(
                prompt_tokens=token_usage_dict.get("prompt_tokens", 0),
                completion_tokens=token_usage_dict.get("completion_tokens", 0),
                total_tokens=token_usage_dict.get("total_tokens", 0)
            )
            
            response = QueryGenerateResponseData(
                query_id=query_id,
                ai_response=generated_text_response,
                retrieved_documents=retrieved_docs_for_response,
                llm_model_info=llm_info_for_response,
                usage=token_usage_for_response,
                search_time_ms=search_time_ms,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms,
                metadata={
                    "original_query_text": query_text,
                    "collections_searched": collection_ids,
                    "top_k_retrieval_used": top_k_eff,
                    "similarity_threshold_used": similarity_threshold_eff
                }
                # timestamp is default_factory
            )
            
            self._logger.info(
                f"Consulta RAG completada en {total_time_ms}ms",
                extra={
                    "query_id": query_id,
                    "search_time_ms": search_time_ms,
                    "generation_time_ms": generation_time_ms,
                    "results_count": len(search_results)
                }
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error en procesamiento RAG: {e}", exc_info=True)
            raise ExternalServiceError(
                f"Error procesando consulta RAG: {str(e)}",
                original_exception=e
            )
    
    async def _get_query_embedding(
        self, 
        query_text: str, 
        tenant_id: str, 
        session_id: str,
        trace_id: Optional[UUID],
        embedding_client,
        task_id: Optional[UUID]
    ) -> List[float]:
        """
        Obtiene el embedding de la consulta.
        """
        # Si tenemos un cliente de embedding, usarlo
        if embedding_client:
            try:
                self._logger.debug("Solicitando embedding al Embedding Service")
                response = await embedding_client.request_query_embedding(
                    query_text=query_text,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    task_id=task_id,
                    trace_id=trace_id
                )
                # Asumiendo que la respuesta tiene un campo 'embedding' en data
                return response.data.get("embedding", [])
            except Exception as e:
                self._logger.warning(f"Error obteniendo embedding del servicio: {e}")
                # Continuar con embedding simulado
        
        # Simulación: generar un vector aleatorio normalizado
        self._logger.debug("Generando embedding simulado para la consulta")
        import random
        embedding_dim = 1536  # Dimensión típica de embeddings
        embedding = [random.gauss(0, 1) for _ in range(embedding_dim)]
        
        # Normalizar
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    async def _search_documents(
        self,
        query_text: str,
        query_embedding: List[float],
        collection_ids: List[str],
        top_k: int,
        similarity_threshold: float,
        tenant_id: str
    ) -> List[SearchResultData]:
        """
        Busca documentos relevantes en las colecciones especificadas.
        """
        try:
            # Buscar en vector store
            results = await self.vector_client.search(
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id
            )
            
            return results
            
        except Exception as e:
            self._logger.error(f"Error en búsqueda vectorial: {e}")
            raise ExternalServiceError(
                "Error al buscar documentos en el vector store",
                original_exception=e
            )
    
    def _build_rag_prompt(
        self,
        query_text: str,
        search_results: List[SearchResultData],
        conversation_history: Optional[List[QueryServiceChatMessage]] = None
    ) -> str:
        """
        Construye el prompt para el LLM con el contexto recuperado.
        """
        # Construir contexto desde los resultados
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[Documento {i} - Score: {result.similarity_score:.2f}]\n"
                f"Colección: {result.collection_id}\n"
                f"Contenido: {result.content}\n"
            )
        
        context = "\n---\n".join(context_parts)
        
        # Construir prompt
        prompt_parts = []
        
        # Agregar historial si existe
        if conversation_history:
            prompt_parts.append("HISTORIAL DE CONVERSACIÓN:")
            for msg in conversation_history[-5:]:  # Últimos 5 mensajes
                prompt_parts.append(f"{msg.role.upper()}: {msg.content}")
            prompt_parts.append("")
        
        # Agregar contexto
        prompt_parts.append("CONTEXTO RELEVANTE:")
        prompt_parts.append(context)
        prompt_parts.append("")
        
        # Agregar pregunta
        prompt_parts.append("PREGUNTA ACTUAL:")
        prompt_parts.append(query_text)
        prompt_parts.append("")
        prompt_parts.append("Por favor, responde la pregunta basándote en el contexto proporcionado. Si la información en el contexto no es suficiente para responder completamente, indícalo claramente.")
        
        return "\n".join(prompt_parts)
    
    def _get_default_system_prompt(self) -> str:
        """
        Retorna el prompt de sistema por defecto.
        """
        return (
            "Eres un asistente útil que responde preguntas basándose en el contexto proporcionado. "
            "Siempre cita la información relevante del contexto cuando sea posible. "
            "Si el contexto no contiene información suficiente para responder la pregunta, "
            "indícalo claramente. No inventes información que no esté en el contexto."
        )
    
    async def _generate_response(
        self,
        prompt: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: Optional[float],             # Added
        frequency_penalty: Optional[float], # Added
        presence_penalty: Optional[float]   # Added
    ) -> tuple[str, Dict[str, int]]:
        """
        Genera la respuesta usando el LLM.
        
        Returns:
            Tupla de (respuesta, uso_de_tokens)
        """
        try:
            # Validar que el modelo esté disponible
            if model not in self.available_models:
                self._logger.warning(f"Modelo {model} no está en la lista de disponibles ({self.available_models}), usando default {self.default_llm_model}")
                model = self.default_llm_model
            
            response, token_usage = await self.groq_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p, # Use passed value (GroqClient handles default if None)
                frequency_penalty=frequency_penalty, # Use passed value
                presence_penalty=presence_penalty # Use passed value
            )
            
            return response, token_usage
            
        except Exception as e:
            self._logger.error(f"Error generando respuesta con LLM: {e}")
            raise ExternalServiceError(
                f"Error al generar respuesta con {model}",
                original_exception=e
            )