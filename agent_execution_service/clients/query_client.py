"""
Cliente para interactuar con Query Service usando Domain Actions.

# TODO: Oportunidades de mejora futura:
# 1. Implementar un BaseClient compartido con QueryClient del Query Service
# 2. Estandarizar más la conversión entre modelos específicos y DomainAction genérico
# 3. Añadir manejo avanzado de errors con retries
# 4. Centralizar la configuración de nombres de colas para evitar inconsistencias
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from common.models.execution_context import ExecutionContext
from common.redis_pool import get_redis_client
from agent_execution_service.config.settings import get_settings

# Importamos los modelos específicos de acciones
from query_service.models.actions import QueryGenerateAction, SearchDocsAction

logger = logging.getLogger(__name__)
settings = get_settings()

class QueryClient:
    """
    Cliente para enviar solicitudes al Query Service.
    
    Permite al Agent Execution Service enviar solicitudes de generación
    de respuestas RAG y búsqueda de documentos de forma asíncrona.
    Utiliza DomainQueueManager para comunicación enriquecida con contexto.
    """
    
    def __init__(self, queue_manager: Optional[DomainQueueManager] = None):
        """
        Inicializa el cliente.
        
        Args:
            action_processor: Procesador de acciones (opcional)
        """
        redis_client = get_redis_client(settings.redis_url)
        self.queue_manager = queue_manager or DomainQueueManager(redis_client)
        self.callback_queue = f"execution.{settings.service_id}.callbacks"
    
    async def generate_query(
        self,
        tenant_id: str,
        query: str,
        query_embedding: List[float],
        collection_id: str,
        task_id: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        agent_id: Optional[str] = None,
        agent_description: Optional[str] = None,
        similarity_top_k: int = 5,
        relevance_threshold: float = 0.7,
        llm_model: Optional[str] = None,
        include_sources: bool = True,
        max_sources: Optional[int] = None,
        fallback_behavior: str = "use_agent_knowledge",
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> str:
        """
        Solicita generación de respuesta RAG.
        
        Args:
            tenant_id: ID del tenant
            query: Query del usuario
            query_embedding: Vector embedding de la query
            collection_id: ID de colección de documentos
            task_id: ID de tarea (opcional)
            conversation_id: ID de conversación (opcional)
            agent_id: ID del agente (opcional)
            agent_description: Descripción del agente (opcional)
            similarity_top_k: Número de documentos a recuperar
            relevance_threshold: Umbral de relevancia
            llm_model: Modelo de LLM a usar (opcional)
            include_sources: Incluir fuentes en resultado
            max_sources: Máximo número de fuentes (opcional)
            fallback_behavior: Comportamiento si no hay docs
            metadata: Metadatos adicionales (opcional)
            context: Contexto de ejecución (opcional)
            
        Returns:
            task_id: ID de tarea para seguimiento
            
        Raises:
            Exception: Si hay error al encolar
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        # Crear datos de la acción
        action_data = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "session_id": str(conversation_id) if conversation_id else task_id,
            "callback_queue": self.callback_queue,
            "query": query,
            "query_embedding": query_embedding,
            "collection_id": collection_id,
            "agent_id": agent_id,
            "agent_description": agent_description,
            "similarity_top_k": similarity_top_k,
            "relevance_threshold": relevance_threshold,
            "llm_model": llm_model,
            "include_sources": include_sources,
            "max_sources": max_sources,
            "fallback_behavior": fallback_behavior,
            "metadata": metadata or {}
        }
        
        # Crear DomainAction
        domain_action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="query.generate",
            task_id=task_id,
            tenant_id=tenant_id,
            data=action_data
        )
        
        if context:
            # Usar enqueue_execution con contexto si está disponible
            logger.info(f"Encolando acción de query con contexto, tenant_tier: {context.tenant_tier}")
            await self.queue_manager.enqueue_execution(
                action=domain_action,
                context=context
            )
        else:
            # Fallback a enqueue sin contexto
            await self.queue_manager.enqueue(
                action=domain_action,
                domain="query",
                tenant_id=tenant_id
            )
            
        logger.info(f"Acción de query encolada: {task_id}")
        return task_id
    
    async def search_docs(
        self,
        tenant_id: str,
        collection_id: str,
        query_embedding: List[float],
        task_id: Optional[str] = None,
        limit: int = 5,
        similarity_threshold: float = 0.7,
        metadata_filter: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> str:
        """
        Solicita búsqueda de documentos por embedding.
        
        Args:
            tenant_id: ID del tenant
            collection_id: ID de colección de documentos
            query_embedding: Vector embedding de búsqueda
            task_id: ID de tarea (opcional)
            limit: Número máximo de resultados
            similarity_threshold: Umbral de similitud
            metadata_filter: Filtro de metadatos (opcional)
            metadata: Metadatos adicionales (opcional)
            context: Contexto de ejecución (opcional)
            
        Returns:
            task_id: ID de tarea para seguimiento
            
        Raises:
            Exception: Si hay error al encolar
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        # Crear datos de la acción
        action_data = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "session_id": task_id,
            "callback_queue": self.callback_queue,
            "collection_id": collection_id,
            "query_embedding": query_embedding,
            "limit": limit,
            "similarity_threshold": similarity_threshold,
            "metadata_filter": metadata_filter or {},
            "metadata": metadata or {}
        }
        
        # Crear DomainAction
        domain_action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="query.search",
            task_id=task_id,
            tenant_id=tenant_id,
            data=action_data
        )
        
        if context:
            # Usar enqueue_execution con contexto si está disponible
            logger.info(f"Encolando acción de búsqueda con contexto, tenant_tier: {context.tenant_tier}")
            await self.queue_manager.enqueue_execution(
                action=domain_action,
                context=context
            )
        else:
            # Fallback a enqueue sin contexto
            await self.queue_manager.enqueue(
                action=domain_action,
                domain="query",
                tenant_id=tenant_id
            )
            
        logger.info(f"Acción de búsqueda encolada: {task_id}")
        return task_id
