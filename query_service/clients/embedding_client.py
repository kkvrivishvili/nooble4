"""
Cliente para comunicarse con el Embedding Service.

Utiliza BaseRedisClient para enviar DomainActions al
Embedding Service cuando se necesitan generar embeddings.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from common.models import DomainAction, DomainActionResponse
from common.clients import BaseRedisClient


class EmbeddingClient:
    """
    Cliente para solicitar embeddings al Embedding Service.
    
    Envía DomainActions asíncronas al Embedding Service y
    puede esperar respuestas mediante callbacks.
    """
    
    def __init__(self, redis_client: BaseRedisClient):
        """
        Inicializa el cliente con un BaseRedisClient.
        
        Args:
            redis_client: Cliente Redis para enviar acciones
        """
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)
    
    async def request_embeddings(
        self,
        texts: List[str],
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        callback_queue: Optional[str] = None
    ) -> str:
        """
        Solicita embeddings para una lista de textos.
        
        Args:
            texts: Textos para generar embeddings
            tenant_id: ID del tenant
            session_id: ID de sesión
            task_id: ID de la tarea
            trace_id: ID de traza
            model: Modelo de embedding específico (string, no enum)
            dimensions: Dimensiones del embedding
            callback_queue: Cola para recibir el resultado
            
        Returns:
            ID de la acción enviada
        """
        # Crear payload compatible con EmbeddingRequest
        embedding_request = {
            "input": texts,
            "model": model or "text-embedding-3-small",
            "dimensions": dimensions,
            "encoding_format": "float"
        }
        
        # Crear DomainAction
        action = DomainAction(
            action_id=uuid4(),
            action_type="embedding.generate",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            user_id=None,  # Query service actúa como sistema
            origin_service=self.redis_client.service_name,
            trace_id=trace_id,
            data=embedding_request,
            callback_queue_name=callback_queue,
            callback_action_type="embedding.result" if callback_queue else None
        )
        
        # Enviar acción
        if callback_queue:
            # Asíncrono con callback
            await self.redis_client.send_action_async_with_callback(
                action=action,
                callback_event_name="embedding.result"
            )
        else:
            # Fire and forget
            await self.redis_client.send_action_async(action)
        
        self.logger.info(
            f"Solicitud de embeddings enviada: {action.action_id} "
            f"para {len(texts)} textos"
        )
        
        return str(action.action_id)
    
    async def request_query_embedding(
        self,
        query_text: str,
        tenant_id: str,
        session_id: str,
        task_id: UUID,
        trace_id: UUID,
        model: Optional[str] = None,
        dimensions: Optional[int] = None
    ) -> DomainActionResponse:
        """
        Solicita embedding para una consulta específica.
        
        Este es un método de conveniencia para solicitar un
        único embedding de forma pseudo-síncrona.
        
        Args:
            query_text: Texto de la consulta
            tenant_id: ID del tenant
            session_id: ID de sesión
            task_id: ID de la tarea
            trace_id: ID de traza
            model: Modelo de embedding (string)
            dimensions: Dimensiones del embedding
            
        Returns:
            DomainActionResponse con el embedding
        """
        # Crear payload compatible con EmbeddingRequest
        embedding_request = {
            "input": query_text,  # Para single query, input es un string
            "model": model or "text-embedding-3-small",
            "dimensions": dimensions,
            "encoding_format": "float"
        }
        
        # Crear DomainAction con correlation_id para pseudo-sync
        action = DomainAction(
            action_id=uuid4(),
            action_type="embedding.generate_query",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            user_id=None,
            origin_service=self.redis_client.service_name,
            correlation_id=uuid4(),  # Para pseudo-sync
            trace_id=trace_id,
            data=embedding_request
        )
        
        # Enviar y esperar respuesta
        response = await self.redis_client.send_action_pseudo_sync(
            action=action,
            timeout=30  # 30 segundos de timeout
        )
        
        if not response.success:
            error_msg = f"Error obteniendo embedding: {response.error.message if response.error else 'Unknown error'}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        
        return response