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

from ..models.payloads import (
    QueryGenerateResponse,
    SearchResult
)
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
        self.groq_client = GroqClient(api_key=app_settings.groq_api_key)
        self.vector_client = VectorClient(
            base_url=app_settings.vector_db_url,
            timeout=app_settings.http_timeout_seconds
        )
        
        # Configuración
        self.default_top_k = app_settings.default_top_k
        self.similarity_threshold = app_settings.similarity_threshold
        self.default_llm_model = app_settings.default_llm_model
        self.llm_temperature = app_settings.llm_temperature
        self.llm_max_tokens = app_settings.llm_max_tokens
        
        self._logger.info("RAGHandler inicializado")
    
    async def process_rag_query(
        self,
        query_text: str,
        collection_ids: List[str],
        tenant_id: str,
        session_id: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        llm_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        trace_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        embedding_client=None,
        task_id: Optional[UUID] = None
    ) -> QueryGenerateResponse:
        """
        Procesa una consulta RAG completa.
        
        Args:
            query_text: Texto de la consulta
            collection_ids: IDs de colecciones donde buscar
            tenant_id: ID del tenant
            session_id: ID de sesión
            top_k: Número de resultados a recuperar
            similarity_threshold: Umbral de similitud mínimo
            llm_model: Modelo LLM a usar
            temperature: Temperatura para generación
            max_tokens: Máximo de tokens
            system_prompt: Prompt de sistema personalizado
            conversation_history: Historial de conversación
            trace_id: ID de traza
            correlation_id: ID de correlación
            embedding_client: Cliente para obtener embeddings
            task_id: ID de la tarea
            
        Returns:
            QueryGenerateResponse con la respuesta generada
        """
        start_time = time.time()
        query_id = str(correlation_id) if correlation_id else str(UUID())
        
        # Usar valores por defecto si no se especifican
        top_k = top_k or self.default_top_k
        similarity_threshold = similarity_threshold or self.similarity_threshold
        llm_model = llm_model or self.default_llm_model
        temperature = temperature if temperature is not None else self.llm_temperature
        max_tokens = max_tokens or self.llm_max_tokens
        
        self._logger.info(
            f"Procesando consulta RAG: '{query_text[:50]}...' en colecciones {collection_ids}",
            extra={
                "query_id": query_id,
                "tenant_id": tenant_id,
                "collections": collection_ids
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
            
            # 2. Buscar documentos relevantes
            search_results = await self._search_documents(
                query_text=query_text,
                query_embedding=query_embedding,
                collection_ids=collection_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id
            )
            search_time_ms = int((time.time() - search_start) * 1000)
            
            # 3. Construir prompt con contexto
            prompt = self._build_rag_prompt(
                query_text=query_text,
                search_results=search_results,
                conversation_history=conversation_history
            )
            
            # 4. Generar respuesta
            generation_start = time.time()
            generated_response, token_usage = await self._generate_response(
                prompt=prompt,
                system_prompt=system_prompt or self._get_default_system_prompt(),
                model=llm_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            generation_time_ms = int((time.time() - generation_start) * 1000)
            
            # 5. Construir respuesta
            total_time_ms = int((time.time() - start_time) * 1000)
            
            response = QueryGenerateResponse(
                query_id=query_id,
                query_text=query_text,
                generated_response=generated_response,
                search_results=search_results,
                llm_model=llm_model,
                temperature=temperature,
                prompt_tokens=token_usage.get("prompt_tokens"),
                completion_tokens=token_usage.get("completion_tokens"),
                total_tokens=token_usage.get("total_tokens"),
                search_time_ms=search_time_ms,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms,
                metadata={
                    "collections_searched": collection_ids,
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold
                }
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
    ) -> List[SearchResult]:
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
        search_results: List[SearchResult],
        conversation_history: Optional[List[Dict[str, str]]] = None
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
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.upper()}: {content}")
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
        max_tokens: int
    ) -> tuple[str, Dict[str, int]]:
        """
        Genera la respuesta usando el LLM.
        
        Returns:
            Tupla de (respuesta, uso_de_tokens)
        """
        try:
            response, token_usage = await self.groq_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response, token_usage
            
        except Exception as e:
            self._logger.error(f"Error generando respuesta con LLM: {e}")
            raise ExternalServiceError(
                f"Error al generar respuesta con {model}",
                original_exception=e
            )