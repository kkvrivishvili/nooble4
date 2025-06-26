"""
Cliente para comunicarse con el Embedding Service.

Utiliza BaseRedisClient para enviar DomainActions al
Embedding Service cuando se necesitan generar embeddings.
"""

import logging
from typing import List
from uuid import UUID, uuid4

from common.models import DomainAction, DomainActionResponse
from common.models.config_models import RAGConfig
from common.clients import BaseRedisClient

class EmbeddingClient:
    """
    Cliente para solicitar embeddings al Embedding Service.
    
    Envía DomainActions asíncronas al Embedding Service usando
    configuración centralizada de RAG.
    """
    
    def __init__(self, redis_client: BaseRedisClient):
        """
        Inicializa el cliente con un BaseRedisClient.
        
        Args:
            redis_client: Cliente Redis para enviar acciones
        """
        self.redis_client = redis_client
        self._logger = logging.getLogger(__name__)
    
    async def get_embeddings(
        self,
        texts: List[str],
        rag_config: RAGConfig,
        tenant_id: UUID,
        session_id: UUID,
        task_id: UUID,
        agent_id: UUID,
        trace_id: UUID
    ) -> DomainActionResponse:
        """
        Solicita embeddings para una lista de textos usando configuración RAG.
        
        Args:
            texts: Textos para generar embeddings
            rag_config: Configuración RAG con modelo y dimensiones
            tenant_id: ID del tenant
            session_id: ID de sesión  
            task_id: ID de la tarea
            agent_id: ID del agente (obligatorio)
            trace_id: ID de traza
            
        Returns:
            DomainActionResponse con los embeddings
        """
        # Payload solo con los textos (datos puros)
        payload = {
            "texts": texts  # Solo los datos
        }
        
        # Crear DomainAction con correlation_id para pseudo-sync
        action = DomainAction(
            action_id=uuid4(),
            action_type="embedding.generate",
            tenant_id=tenant_id,
            session_id=session_id,
            task_id=task_id,
            agent_id=agent_id,
            user_id=None,  # Query service actúa como sistema
            origin_service="query",
            correlation_id=uuid4(),  # Para pseudo-sync
            trace_id=trace_id,
            rag_config=rag_config,  # Config en el header
            data=payload
        )
        
        self._logger.info(
            f"Solicitando embeddings para {len(texts)} textos",
            extra={
                "action_id": action.action_id,
                "model": rag_config.embedding_model.model_name,
                "dimensions": rag_config.embedding_dimensions,
                "agent_id": agent_id,
                "tenant_id": tenant_id
            }
        )
        
        # Enviar y esperar respuesta con timeout configurado
        response = await self.redis_client.send_action_pseudo_sync(
            action=action,
            timeout=30  # 30 segundos de timeout
        )
        
        if not response.success:
            error_msg = f"Error obteniendo embeddings: {response.error.message if response.error else 'Unknown error'}"
            self._logger.error(
                error_msg,
                extra={
                    "action_id": action.action_id,
                    "agent_id": agent_id,
                    "model": rag_config.embedding_model.model_name
                }
            )
            raise Exception(error_msg)
        
        self._logger.info(
            f"Embeddings generados exitosamente",
            extra={
                "action_id": action.action_id,
                "agent_id": agent_id,
                "texts_count": len(texts)
            }
        )
        
        return response