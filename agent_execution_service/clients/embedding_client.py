"""
Cliente para comunicarse con Embedding Service usando Domain Actions.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID

from common.models.actions import DomainAction
from common.services.action_processor import ActionProcessor
from common.redis_pool import get_redis_client
from agent_execution_service.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class EmbeddingClient:
    """
    Cliente para solicitar embeddings usando Domain Actions.
    
    Este cliente envía acciones al servicio de embeddings para
    generar o validar embeddings de forma asíncrona.
    """
    
    def __init__(self, action_processor: Optional[ActionProcessor] = None):
        """
        Inicializa el cliente.
        
        Args:
            action_processor: Procesador de acciones (opcional)
        """
        redis_client = get_redis_client(settings.redis_url)
        self.action_processor = action_processor or ActionProcessor(redis_client)
    
    async def generate_embeddings(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        model: Optional[str] = None,
        task_id: Optional[str] = None,
        collection_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
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
        
        # Crear acción
        embedding_action = DomainAction(
            action_type="embedding.generate",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            callback_queue=callback_queue,
            texts=texts,
            model=model,
            collection_id=collection_id,
            metadata=metadata
        )
        
        # Encolar acción
        queue_name = f"embedding.{tenant_id}.actions"
        success = await self.action_processor.enqueue_action(embedding_action, queue_name)
        
        if not success:
            logger.error(f"Error encolando acción de embedding: {task_id}")
            raise Exception("Error al solicitar embeddings")
        
        logger.info(f"Acción de embedding encolada: {task_id}")
        return task_id
    
    async def validate_texts(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        callback_queue: str,
        model: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> str:
        """
        Solicita la validación de textos.
        
        Args:
            texts: Textos para validar
            tenant_id: ID del tenant
            session_id: ID de la sesión
            callback_queue: Cola para recibir el callback
            model: Modelo a validar contra (default si no se especifica)
            task_id: ID de la tarea (opcional)
            
        Returns:
            task_id: ID de la tarea para seguimiento
            
        Raises:
            Exception: Si hay un error encolando la acción
        """
        # Crear ID único si no se proporciona
        task_id = task_id or str(uuid.uuid4())
        
        # Crear acción
        validate_action = DomainAction(
            action_type="embedding.validate",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            callback_queue=callback_queue,
            texts=texts,
            model=model
        )
        
        # Encolar acción
        queue_name = f"embedding.{tenant_id}.actions"
        success = await self.action_processor.enqueue_action(validate_action, queue_name)
        
        if not success:
            logger.error(f"Error encolando acción de validación: {task_id}")
            raise Exception("Error al solicitar validación de textos")
        
        logger.info(f"Acción de validación encolada: {task_id}")
        return task_id
