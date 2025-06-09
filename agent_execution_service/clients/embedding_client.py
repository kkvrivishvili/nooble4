"""
Cliente para comunicarse con Embedding Service usando Domain Actions.
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

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingClient:
    """
    Cliente para solicitar embeddings usando Domain Actions.
    
    Este cliente envía acciones al servicio de embeddings para
    generar o validar embeddings de forma asíncrona.
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
    
    async def generate_embeddings(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        model: Optional[str] = None,
        task_id: Optional[str] = None,
        collection_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> str:
        """
        Solicita la generación de embeddings.
        
        Args:
            texts: Textos para generar embeddings
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola para recibir el callback
            model: Modelo a utilizar (default si no se especifica)
            task_id: ID de la tarea (opcional)
            collection_id: ID de la colección (opcional)
            metadata: Metadatos adicionales (opcional)
            
        Returns:
            task_id: ID de la tarea para seguimiento
            
        Raises:
            Exception: Si hay un error encolando la acción
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="embedding.generate",
            task_id=task_id,
            tenant_id=tenant_id,
            data={
                "texts": texts,
                "session_id": session_id,
                "callback_queue": callback_queue,
                "model": model,
                "collection_id": str(collection_id) if collection_id else None,
                "metadata": metadata or {}
            }
        )
        
        if context:
            # Usar enqueue_execution con contexto si está disponible
            logger.info(f"Encolando acción con contexto, tenant_tier: {context.tenant_tier}")
            await self.queue_manager.enqueue_execution(
                action=action,
                context=context
            )
        else:
            # Fallback a enqueue sin contexto
            await self.queue_manager.enqueue(
                action=action,
                domain="embedding",
                tenant_id=tenant_id
            )
            
        return task_id
    
    async def validate_embeddings(
        self,
        embedding_ids: List[str],
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ExecutionContext] = None
    ) -> str:
        """
        Solicita la validación de embeddings.
        
        Args:
            embedding_ids: IDs de los embeddings para validar
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola para recibir el callback
            task_id: ID de la tarea (opcional)
            metadata: Metadatos adicionales (opcional)
            context: Contexto de ejecución (opcional)
            
        Returns:
            task_id: ID de la tarea para seguimiento
            
        Raises:
            Exception: Si hay un error encolando la acción
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        action = DomainAction(
            action_id=str(uuid.uuid4()),
            action_type="embedding.validate",
            task_id=task_id,
            tenant_id=tenant_id,
            data={
                "embedding_ids": embedding_ids,
                "session_id": session_id,
                "callback_queue": callback_queue,
                "metadata": metadata or {}
            }
        )
        
        if context:
            # Usar enqueue_execution con contexto si está disponible
            logger.info(f"Encolando validación con contexto, tenant_tier: {context.tenant_tier}")
            await self.queue_manager.enqueue_execution(
                action=action,
                context=context
            )
        else:
            # Fallback a enqueue sin contexto
            await self.queue_manager.enqueue(
                action=action,
                domain="embedding",
                tenant_id=tenant_id
            )
            
        logger.info(f"Acción de validación encolada: {task_id}")
        return task_id
