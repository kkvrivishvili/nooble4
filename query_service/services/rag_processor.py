"""
RAG Processor - Procesador principal de Retrieval-Augmented Generation.

Coordina la búsqueda vectorial y generación de respuestas.
"""

import logging
import time
from typing import Dict, Any, List, Optional

from common.models.execution_context import ExecutionContext
from query_service.models.actions import QueryGenerateAction
from query_service.clients.groq_client import GroqClient
from query_service.services.vector_search_service import VectorSearchService
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGProcessor:
    """
    Procesador RAG principal.
    
    Coordina búsqueda vectorial y generación de respuestas
    usando LLM con contexto de documentos relevantes.
    """
    
    def __init__(self, vector_search_service: VectorSearchService, redis_client=None):
        """
        Inicializa processor.
        
        Args:
            vector_search_service: Servicio de búsqueda vectorial
            redis_client: Cliente Redis para tracking
        """
        self.vector_search = vector_search_service
        self.redis = redis_client
        
        # Inicializar cliente LLM
        self.groq_client = GroqClient()
    
    async def process_rag_query(
        self,
        action: QueryGenerateAction,
        context: ExecutionContext,
        collection_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Procesa consulta RAG completa.
        
        Args:
            action: Acción de consulta
            context: Contexto de ejecución
            collection_config: Configuración de la colección
            
        Returns:
            Dict con resultado de la consulta RAG
        """
        start_time = time.time()
        
        try:
            logger.info(f"Procesando consulta RAG: {action.query[:50]}...")
            
            # 1. Buscar documentos similares
            search_results = await self.vector_search.search_documents(
                collection_id=action.collection_id,
                tenant_id=context.tenant_id,
                query_embedding=action.query_embedding,
                top_k=action.similarity_top_k,
                similarity_threshold=action.relevance_threshold
            )
            
            # 2. Evaluar calidad de resultados
            relevance_assessment = self._assess_document_relevance(
                search_results, action.relevance_threshold
            )
            
            # 3. Generar respuesta según disponibilidad de documentos
            if relevance_assessment["has_relevant_docs"]:
                # Flujo RAG normal con documentos relevantes
                response = await self._generate_rag_response(
                    action, search_results, context
                )
            elif relevance_assessment["has_any_docs"] and action.fallback_behavior != "reject_query":
                # Fallback con documentos de baja relevancia
                response = await self._generate_fallback_response(
                    action, search_results, context
                )
            elif action.fallback_behavior == "use_agent_knowledge":
                # Usar conocimiento del agente sin documentos
                response = await self._generate_agent_knowledge_response(
                    action, context
                )
            else:
                # Rechazar consulta sin documentos
                response = self._generate_rejection_response()
            
            # 4. Preparar fuentes si se requieren
            sources = []
            if action.include_sources and search_results:
                sources = self._format_sources(
                    search_results, action.max_sources
                )
            
            # 5. Construir resultado final
            processing_time = time.time() - start_time
            
            result = {
                "response": response,
                "sources": sources,
                "metadata": {
                    "query": action.query,
                    "collection_id": action.collection_id,
                    "found_documents": len(search_results),
                    "used_documents": min(action.similarity_top_k, len(search_results)),
                    "processing_time": processing_time,
                    "relevance_assessment": relevance_assessment,
                    "model_used": action.llm_model or settings.default_llm_model,
                    "agent_id": action.agent_id,
                    "conversation_id": str(action.conversation_id) if action.conversation_id else None,
                    "fallback_used": not relevance_assessment["has_relevant_docs"]
                }
            }
            
            logger.info(f"Consulta RAG procesada en {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error en proceso RAG: {str(e)}")
            raise
    
    def _assess_document_relevance(
        self, 
        search_results: List[Dict[str, Any]], 
        relevance_threshold: float
    ) -> Dict[str, Any]:
        """Evalúa la relevancia de los documentos encontrados."""
        
        if not search_results:
            return {
                "has_any_docs": False,
                "has_relevant_docs": False,
                "quality": "none",
                "avg_similarity": 0.0
            }
        
        # Calcular similitud promedio
        similarities = [doc.get("similarity", 0.0) for doc in search_results]
        avg_similarity = sum(similarities) / len(similarities)
        
        # Verificar si hay documentos que superen el umbral
        relevant_docs = [doc for doc in search_results if doc.get("similarity", 0.0) > relevance_threshold]
        
        # Determinar calidad
        if relevant_docs:
            quality = "high"
        elif avg_similarity > relevance_threshold * 0.8:  # 80% del umbral
            quality = "medium"
        else:
            quality = "low"
        
        return {
            "has_any_docs": True,
            "has_relevant_docs": len(relevant_docs) > 0,
            "quality": quality,
            "avg_similarity": avg_similarity,
            "relevant_count": len(relevant_docs)
        }
    
    async def _generate_rag_response(
        self,
        action: QueryGenerateAction,
        search_results: List[Dict[str, Any]],
        context: ExecutionContext
    ) -> str:
        """Genera respuesta RAG con documentos relevantes."""
        
        # Construir contexto de documentos
        context_parts = []
        for i, doc in enumerate(search_results[:action.similarity_top_k]):
            context_parts.append(f"[Documento {i+1}]:\n{doc['content']}\n")
        
        document_context = "\n".join(context_parts)
        
        # System prompt para RAG estricto
        system_prompt = """Eres un asistente útil que responde preguntas basándose ÚNICAMENTE en el contexto proporcionado. 
Si la información no está en el contexto, di que no tienes esa información específica."""
        
        # Prompt principal
        prompt = f"""Contexto:
{document_context}

Pregunta: {action.query}

Responde basándote SOLO en el contexto anterior:"""
        
        # Generar respuesta
        response = await self.groq_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=action.llm_model
        )
        
        return response
    
    async def _generate_fallback_response(
        self,
        action: QueryGenerateAction,
        search_results: List[Dict[str, Any]],
        context: ExecutionContext
    ) -> str:
        """Genera respuesta fallback con documentos de baja relevancia."""
        
        # Construir contexto con advertencia de baja relevancia
        context_parts = []
        for i, doc in enumerate(search_results[:action.similarity_top_k]):
            context_parts.append(f"[Documento {i+1}]:\n{doc['content']}\n")
        
        document_context = "\n".join(context_parts)
        
        # System prompt para fallback
        system_prompt = f"""Eres un asistente útil que representa a un agente.
{action.agent_description or 'Tu objetivo es proporcionar información precisa y útil.'}
Se te ha proporcionado algo de contexto, pero podría no ser directamente relevante a la pregunta.
Responde basándote principalmente en tu conocimiento del agente, usando el contexto solo si es útil."""
        
        # Prompt con advertencia
        prompt = f"""Contexto (posiblemente no directamente relevante):
{document_context}

Pregunta: {action.query}

Responde basándote principalmente en tu conocimiento del agente, usando el contexto solo si es útil:"""
        
        # Generar respuesta
        response = await self.groq_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=action.llm_model
        )
        
        return response
    
    async def _generate_agent_knowledge_response(
        self,
        action: QueryGenerateAction,
        context: ExecutionContext
    ) -> str:
        """Genera respuesta usando solo conocimiento del agente."""
        
        # System prompt para conocimiento de agente
        system_prompt = f"""Eres un asistente útil que representa a un agente.
{action.agent_description or 'Tu objetivo es proporcionar información precisa y útil.'}
Responde según tu conocimiento sobre el propósito y funcionalidad del agente.
Si no puedes responder con confianza, indícalo claramente."""
        
        # Prompt simple
        prompt = f"Pregunta: {action.query}\n\nResponde según tu conocimiento sobre el propósito y funcionalidad del agente."
        
        # Generar respuesta
        response = await self.groq_client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=action.llm_model
        )
        
        return response
    
    def _generate_rejection_response(self) -> str:
        """Genera respuesta de rechazo cuando no hay documentos."""
        return "No dispongo de información suficiente para responder a esta pregunta."
    
    def _format_sources(
        self, 
        search_results: List[Dict[str, Any]], 
        max_sources: int
    ) -> List[Dict[str, Any]]:
        """Formatea fuentes para incluir en respuesta."""
        sources = []
        
        for doc in search_results[:max_sources]:
            source = {
                "content": doc["content"][:500] + "..." if len(doc["content"]) > 500 else doc["content"],
                "metadata": doc.get("metadata", {}),
                "similarity": doc.get("similarity", 0.0)
            }
            sources.append(source)
        
        return sources