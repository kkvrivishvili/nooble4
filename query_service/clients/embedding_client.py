"""
Cliente para comunicarse con Embedding Service usando Domain Actions.
MODIFICADO: Integración con sistema de colas por tier.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID

from common.models.actions import DomainAction
from common.services.domain_queue_manager import DomainQueueManager
from common.redis_pool import get_redis_client
from embedding_service.models.actions import EmbeddingGenerateAction
from query_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingClient:
    """
    Cliente para solicitar embeddings usando Domain Actions.
    MODIFICADO: Usar DomainQueueManager en lugar de ActionProcessor.
    """
    
    def __init__(self, queue_manager: Optional[DomainQueueManager] = None):
        """
        Inicializa el cliente.
        
        Args:
            queue_manager: Gestor de colas por tier (opcional)
        """
        if queue_manager:
            self.queue_manager = queue_manager
        else:
            redis_client = get_redis_client(settings.redis_url)
            self.queue_manager = DomainQueueManager(redis_client)
    
    async def generate_embeddings(
        self,
        texts: List[str],
        tenant_id: str,
        tenant_tier: str,
        session_id: str,
        callback_queue: str,
        model: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Solicita la generación de embeddings.
        
        Args:
            texts: Textos para generar embeddings
            tenant_id: ID del tenant
            tenant_tier: Tier del tenant
            session_id: ID de la sesión
            callback_queue: Cola para recibir el callback
            model: Modelo a utilizar (default si no se especifica)
            task_id: ID de la tarea (opcional)
            metadata: Metadatos adicionales (opcional)
            
        Returns:
            task_id: ID de la tarea para seguimiento
            
        Raises:
            Exception: Si hay un error encolando la acción
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        # Crear contexto básico para embedding
        from common.models.execution_context import ExecutionContext
        context = ExecutionContext(
            context_id=f"query-embedding-{task_id}",
            context_type="query",
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,
            primary_agent_id="query-service",
            agents=["query-service"],
            collections=[],
            metadata=metadata or {}
        )
        
        # Crear acción usando modelo específico
        embedding_action = EmbeddingGenerateAction(
            task_id=task_id,
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,
            session_id=session_id,
            execution_context=context.to_dict(),
            callback_queue=callback_queue,
            texts=texts,
            model=model,
            metadata=metadata or {}
        )
        
        # Encolar usando DomainQueueManager
        queue_name = await self.queue_manager.enqueue_execution(
            action=embedding_action,
            target_domain="embedding",
            context=context
        )
        
        logger.info(f"Acción de embedding encolada en {queue_name}: {task_id}")
        return task_id