"""
Handler para procesar Domain Actions de Query Service.

# TODO: Oportunidades de mejora futura:
# 1. Implementar manejo de errores estandarizado usando clases de error específicas
# 2. Añadir mecanismos de retry con backoff exponencial para llamadas API externas
# 3. Mejorar validación de parámetros de entrada antes de procesar
# 4. Considerar extraer un BaseHandler para funcionalidad común entre handlers
"""

import logging
import time
from typing import Dict, Any, List, Optional

from query_service.models.actions import QueryGenerateAction, SearchDocsAction
from query_service.clients.groq_client import GroqClient
from query_service.clients.vector_store_client import VectorStoreClient
from query_service.config.settings import get_settings
from common.errors import ServiceError

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryHandler:
    """
    Handler para procesar acciones de query y búsqueda.
    """
    
    def __init__(self):
        """Inicializa el handler con clientes necesarios."""
        self.groq_client = GroqClient()
        self.vector_store = VectorStoreClient()
    
    async def handle_query_generate(self, action: QueryGenerateAction) -> Dict[str, Any]:
        """
        Procesa una acción de generación de consulta RAG.
        
        Args:
            action: Acción de consulta
            
        Returns:
            Dict con resultado del procesamiento
            
        Raises:
            Exception: Si hay errores en el procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando consulta RAG para tarea {task_id}")
            
            # 1. Buscar documentos similares
            similar_docs = await self.vector_store.search_by_embedding(
                tenant_id=action.tenant_id,
                collection_id=action.collection_id,
                query_embedding=action.query_embedding,
                top_k=action.similarity_top_k,
                threshold=settings.similarity_threshold
            )
            
            # 2. Determinar si hay documentos realmente relevantes
            has_relevant_docs = False
            source_quality = "none"
            
            if similar_docs:
                # Verificar si al menos un documento supera el umbral de relevancia estricto
                has_relevant_docs = any(doc['similarity'] > action.relevance_threshold for doc in similar_docs)
                
                if has_relevant_docs:
                    source_quality = "high"
                else:
                    source_quality = "low"
                    logger.info(f"Documentos encontrados pero por debajo del umbral de relevancia ({action.relevance_threshold})")
            else:
                logger.warning("No se encontraron documentos similares")
            
            # 3. Preparar fuentes para incluir en respuesta si es necesario
            sources = []
            if action.include_sources and similar_docs:
                for i, doc in enumerate(similar_docs[:action.similarity_top_k]):
                    sources.append({
                        "content": doc['content'][:500] + "..." if len(doc['content']) > 500 else doc['content'],
                        "metadata": doc['metadata'],
                        "similarity": doc['similarity']
                    })
            
            # 4. Determinar comportamiento según disponibilidad de información
            if not similar_docs and action.fallback_behavior == "reject_query":
                # Caso 1: No hay documentos y política es rechazar
                return {
                    "success": True,
                    "execution_time": time.time() - start_time,
                    "result": {
                        "response": "No dispongo de información para responder a esta pregunta.",
                        "sources": [],
                        "metadata": {
                            "found_documents": 0,
                            "processing_time": time.time() - start_time,
                            "source_quality": source_quality
                        }
                    }
                }
            
            # 5. Construir prompt y system prompt según escenario
            system_prompt = ""
            prompt = ""
            
            if not similar_docs:
                # Caso 2: No hay documentos pero usamos conocimiento del agente
                system_prompt = f"""Eres un asistente útil que representa a un agente. 
                {action.agent_description or 'Tu objetivo es proporcionar información precisa y útil.'}
                Si no puedes responder con confianza, indícalo claramente."""
                
                prompt = f"Pregunta: {action.query}\n\nResponde según tu conocimiento sobre el propósito y funcionalidad del agente."
                
            elif not has_relevant_docs:
                # Caso 3: Hay documentos pero no son suficientemente relevantes
                system_prompt = f"""Eres un asistente útil que representa a un agente.
                {action.agent_description or 'Tu objetivo es proporcionar información precisa y útil.'}
                Se te ha proporcionado algo de contexto, pero no parece directamente relevante a la pregunta.
                Responde basándote principalmente en tu conocimiento general sobre el agente.
                Si no puedes responder con confianza, indícalo claramente."""
                
                # Incluimos el contexto de todas formas, pero indicamos que podría no ser muy relevante
                context = "\n".join(f"[Documento {i+1}]:\n{doc['content']}\n" for i, doc in enumerate(similar_docs[:action.similarity_top_k]))
                prompt = f"""Contexto (posiblemente no directamente relevante):
{context}

Pregunta: {action.query}

Responde basándote principalmente en tu conocimiento del agente, usando el contexto solo si es útil:"""
                
            else:
                # Caso 4: Hay documentos relevantes (flujo normal RAG)
                system_prompt = """Eres un asistente útil que responde preguntas basándose ÚNICAMENTE en el contexto proporcionado. 
Si la información no está en el contexto, di que no tienes esa información."""
                
                # Construir contexto como lo hacemos actualmente
                context_parts = []
                for i, doc in enumerate(similar_docs[:action.similarity_top_k]):
                    context_parts.append(f"[Documento {i+1}]:\n{doc['content']}\n")
                
                context = "\n".join(context_parts)
                prompt = f"""Contexto:
{context}

Pregunta: {action.query}

Responde basándote SOLO en el contexto anterior:"""
            
            # 6. Generar respuesta con Groq
            response = await self.groq_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=action.llm_model
            )
            
            # 7. Registrar uso de tokens (pendiente implementación completa)
            # Idealmente usar un servicio común de tracking
            
            # 8. Preparar respuesta
            processing_time = time.time() - start_time
            
            result = {
                "response": response,
                "sources": sources if action.include_sources else [],
                "metadata": {
                    "query": action.query,
                    "model": action.llm_model or settings.default_llm_model,
                    "found_documents": len(similar_docs) if similar_docs else 0,
                    "used_documents": min(action.similarity_top_k, len(similar_docs)) if similar_docs else 0,
                    "processing_time": processing_time,
                    "source_quality": source_quality,
                    "avg_similarity": sum(d['similarity'] for d in similar_docs) / len(similar_docs) if similar_docs else 0.0,
                    "agent_id": action.agent_id,
                    "conversation_id": str(action.conversation_id) if action.conversation_id else None
                }
            }
            
            # Limitar fuentes si es necesario
            if action.max_sources and len(result['sources']) > action.max_sources:
                result['sources'] = result['sources'][:action.max_sources]
                
            logger.info(f"Consulta procesada en {processing_time:.2f}s para tarea {task_id}")
            
            return {
                "success": True,
                "execution_time": processing_time,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error en consulta {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
    
    async def handle_search_docs(self, action: SearchDocsAction) -> Dict[str, Any]:
        """
        Procesa una acción de búsqueda de documentos.
        
        Args:
            action: Acción de búsqueda
            
        Returns:
            Dict con resultado del procesamiento
            
        Raises:
            Exception: Si hay errores en el procesamiento
        """
        start_time = time.time()
        task_id = action.task_id
        
        try:
            logger.info(f"Procesando búsqueda para tarea {task_id}")
            
            # Ejecutar búsqueda
            documents = await self.vector_store.search_by_embedding(
                tenant_id=action.tenant_id,
                collection_id=action.collection_id,
                query_embedding=action.query_embedding,
                top_k=action.limit,
                threshold=action.similarity_threshold,
                metadata_filter=action.metadata_filter
            )
            
            # Procesar resultados
            docs_result = []
            for doc in documents:
                docs_result.append({
                    "id": doc.get("id", ""),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "similarity": doc.get("similarity", 0.0)
                })
                
            processing_time = time.time() - start_time
            
            logger.info(f"Búsqueda completada: {len(documents)} docs en {processing_time:.2f}s")
            
            return {
                "success": True,
                "execution_time": processing_time,
                "result": {
                    "documents": docs_result,
                    "metadata": {
                        "found_documents": len(documents),
                        "collection_id": action.collection_id,
                        "processing_time": processing_time
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error en búsqueda {task_id}: {str(e)}")
            return {
                "success": False,
                "execution_time": time.time() - start_time,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
